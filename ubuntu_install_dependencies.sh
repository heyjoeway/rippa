#!/bin/bash

# Auto elevate
if [ $EUID != 0 ]; then
    sudo "$0" "$@"
    exit $?
fi

apt-get update
apt-get install software-properties-common -y
add-apt-repository ppa:heyarje/makemkv-beta -y
apt-get update
apt-get install eject makemkv-bin makemkv-oss ffmpeg abcde cdparanoia python3 python3-pyquery flac -y 