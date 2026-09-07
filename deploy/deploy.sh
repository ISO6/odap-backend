#!/bin/bash

set -e

cd /home/sysadmin/winfred/odap-backend

git pull

uv sync

sudo systemctl restart odap-backend

sudo systemctl status odap-backend