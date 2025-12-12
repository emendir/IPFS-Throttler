#!/bin/bash
## Installation & configuration steps for this project
## OTHER THAN systemd units and moving source code to installation directory
## (that's handled by ./install.sh). 


# get the path of directory this script is currently located in
SCRIPT_DIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

PYTHON_DIR=$SCRIPT_DIR/PythonVenv

sudo mkdir -p $SCRIPT_DIR
sudo chown $USER:$USER $SCRIPT_DIR

virtualenv $PYTHON_DIR
source $PYTHON_DIR/bin/activate

pip install -r $SCRIPT_DIR/requirements.txt


echo "[Unit]
Description=IPFS network effects monitor

[Service]
User=$USER
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=%t/runtime-%u
ExecStart=/usr/bin/bash -c 'source $PYTHON_DIR/bin/activate && python3 $SCRIPT_DIR/src/ipfs_throttler/monitor_and_throttle_ipfs.py'
Restart=always

[Install]
WantedBy=default.target
" | sudo tee /etc/systemd/system/ipfs-throttler

sudo systemctl daemon-reload
sudo systemctl enable ipfs-throttler
sudo systemctl restart ipfs-throttler
