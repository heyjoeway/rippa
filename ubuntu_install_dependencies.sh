#!/bin/bash

# Auto elevate
if [ $EUID != 0 ]; then
    sudo "$0" "$@"
    exit $?
fi

add-apt-repository ppa:heyarje/makemkv-beta -y
apt update
apt install eject makemkv-bin makemkv-oss ffmpeg abcde cdparanoia python3 python3-pyquery flac -y 