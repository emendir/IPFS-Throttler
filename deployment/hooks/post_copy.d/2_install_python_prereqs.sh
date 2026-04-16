#!/bin/bash
## Install python environment for IPFS-Throttler
set -euo --pipefail

if  [ -z $INSTALL_DIR ];then
    echo "The environment INSTALL_DIR has not been set!"
    exit 1
fi

PYTHON_DIR="$INSTALL_DIR/.venv"


virtualenv $PYTHON_DIR
source $PYTHON_DIR/bin/activate

pip install -r $INSTALL_DIR/requirements.txt


