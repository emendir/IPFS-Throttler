#!/usr/bin/env bash
## BashDeploy: Generic project installer
set -euo pipefail

##############################################
# CONFIGURATION
##############################################
SCRIPT_PATH=$(readlink -f "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
PROJ_NAME=$(basename "$SCRIPT_DIR")
DEPLOY_DIR="$SCRIPT_DIR/deployment"
HOOKS_DIR="$DEPLOY_DIR/hooks"
SYSTEMD_DIR="$DEPLOY_DIR/systemd_units"

# Default values (can be overridden by config or env)
DEF_INSTALL_DIR="/opt/$PROJ_NAME"
DEF_SSH_ADDRESS=""
DEF_WITH_SYSTEMD=true
DEF_ENABLE_UNITS=true
DEF_EXCLUDE_FILE="$SCRIPT_DIR/.gitignore"

# Load config file if present
CONFIG_FILE="$SCRIPT_DIR/installer.conf"
if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

##############################################
# HELPERS
##############################################
notify() {
    local message="$1"
    local color="${2:-}\033[0m"
    echo -e "${color}==> ${message}\033[0m"
}

err() {
    echo -e "\033[0;31mERROR: $*\033[0m" >&2
    exit 1
}

run_hook_dir() {
  local dir="$1"
  if [[ -d "$dir" ]]; then
    for script in "$dir"/*.sh; do
      [[ -e "$script" ]] || continue
      notify "Running hook: $(basename "$script")"
      bash "$script"
    done
  fi
}

##############################################
# ARGUMENT PARSING
##############################################
SSH_ADDRESS="$DEF_SSH_ADDRESS"
INSTALL_DIR="$DEF_INSTALL_DIR"
WITH_SYSTEMD="$DEF_WITH_SYSTEMD"
ENABLE_UNITS="$DEF_ENABLE_UNITS"
SSH_OPTS="${SSH_OPTS:-}"
RSYNC_OPTS="${RSYNC_OPTS:-}"
COPY_ONLY="${COPY_ONLY:-}"
EXCLUDE_FILE=$DEF_EXCLUDE_FILE
usage() {
cat <<EOF
BashDeploy

Usage: $0 [OPTIONS]

Options:
  --remote <user@host>   Install on remote machine via SSH
  --dir <path>           Installation directory (default: $DEF_INSTALL_DIR)
  --exclude-from <path>  Installation directory (default: $DEF_EXCLUDE_FILE)
  --with-systemd         Install systemd units (default: $DEF_WITH_SYSTEMD)
  --no-systemd           Skip systemd unit installation
  --enable-units         Enable and start systemd units (default: $DEF_ENABLE_UNITS)
  --no-enable-units      Do not enable/start units after install
  --only-copy            Only copy files to installation target, without running setup/installation scripts
  --help                 Show this help

Find out more at:
https://github.com/emendir/BashDeploy
EOF
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --remote)
      SSH_ADDRESS="$2"; shift 2;;
    --dir)
      INSTALL_DIR="$2"; shift 2;;
    --exclude-from)
      EXCLUDE_FILE="$2"; shift 2;;
    --with-systemd)
      WITH_SYSTEMD=true; shift;;
    --no-systemd)
      WITH_SYSTEMD=false; shift;;
    --enable-units)
      ENABLE_UNITS=true; shift;;
    --no-enable-units)
      ENABLE_UNITS=false; shift;;
    --copy-only)
      COPY_ONLY=true; shift;;
    --help)
      usage; exit 0;;
    *)
      err "Unknown option: $1";;
  esac
done

EXCLUDE_FILE=$(readlink -f $EXCLUDE_FILE)
if ! [ -e $EXCLUDE_FILE ]; then
  touch $EXCLUDE_FILE
fi

# export for availability to hooks
export SSH_ADDRESS
export INSTALL_DIR
export WITH_SYSTEMD
export ENABLE_UNITS
export SSH_OPTS
export RSYNC_OPTS
export COPY_ONLY
export EXCLUDE_FILE

##############################################
# REMOTE INSTALL HANDLING
##############################################
if [[ -n "$SSH_ADDRESS" ]]; then
  notify "Installing remotely on $SSH_ADDRESS"

  # Ensure target directory exists and is owned by the remote user
  ssh $SSH_OPTS "$SSH_ADDRESS" -t "sudo mkdir -p '$INSTALL_DIR' && sudo chown \$USER:\$USER '$INSTALL_DIR'"

  # Copy project files over
  rsync -a $RSYNC_OPTS --delete --exclude-from=$EXCLUDE_FILE -e "ssh $SSH_OPTS" "$SCRIPT_DIR/" "$SSH_ADDRESS:$INSTALL_DIR/"

  if [[ $COPY_ONLY != true ]];then
    # Re-run installer remotely
    ssh $SSH_OPTS "$SSH_ADDRESS" -t "bash '$INSTALL_DIR/$(basename "$SCRIPT_PATH")' --dir '$INSTALL_DIR' \
      $([[ $WITH_SYSTEMD == true ]] && echo --with-systemd || echo --no-systemd) \
      $([[ $ENABLE_UNITS == true ]] && echo --enable-units || echo --no-enable-units)"
    exit 0
  else
    notify "Not installing on remote machine because --copy-only is set."
    exit 0
  fi
fi

##############################################
# LOCAL INSTALLATION
##############################################
notify "Installing locally into $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo rsync -a $RSYNC_OPTS --delete --exclude-from=$EXCLUDE_FILE "$SCRIPT_DIR/" "$INSTALL_DIR/"

# Run post-copy hooks
run_hook_dir "$HOOKS_DIR/post_copy.d"
[[ -x "$HOOKS_DIR/post_copy.sh" ]] && bash "$HOOKS_DIR/post_copy.sh"

##############################################
# SYSTEMD UNIT HANDLING
##############################################
if ! [ -e $SYSTEMD_DIR ]; then
  WITH_SYSTEMD=false
fi
if [[ "$WITH_SYSTEMD" == true ]]; then
  notify "Installing systemd units"

  for scope in system user; do
    UNIT_DIR="$SYSTEMD_DIR/$scope"
    [[ -d "$UNIT_DIR" ]] || continue

    for unit in "$UNIT_DIR"/*.{service,timer,socket,target,mount,automount,path,device,swap,slice,scope}; do
      [[ -e "$unit" ]] || continue

      if [[ $scope == system ]]; then
        sudo cp "$unit" /etc/systemd/system/
      else
        mkdir -p "$HOME/.config/systemd/user"
        cp "$unit" "$HOME/.config/systemd/user/"
      fi
    done
  done
  sudo systemctl daemon-reload
  if [[ "$ENABLE_UNITS" == true ]]; then
    notify "Enabling and starting units"
    for scope in system user; do
      UNIT_DIR="$SYSTEMD_DIR/$scope"
      [[ -d "$UNIT_DIR" ]] || continue
      for unit in "$UNIT_DIR"/*.{service,timer}; do
        [[ -e "$unit" ]] || continue
        if [[ $scope == system ]]; then
          sudo systemctl enable --now "$(basename "$unit")"
        else
          systemctl --user enable --now "$(basename "$unit")"
        fi
      done
    done
  fi

  # Run post-systemd hooks
  run_hook_dir "$HOOKS_DIR/post_systemd.d"
  [[ -x "$HOOKS_DIR/post_systemd.sh" ]] && bash "$HOOKS_DIR/post_systemd.sh"
fi

notify "Installation complete"

