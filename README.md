# Rippa
Automatically rip discs (Data, Redbook, DVD, Blu-Ray) when inserted. When ripping DVDs, each title is automatically transcoded in parallel.

# Security Notice

This script is meant to be run as a user, but does require superuser rights for mounting and ejecting discs. I do not claim to know the full risk of doing this in terms of security and it is up to the user to ensure their environment is safe to allow this in. Please open issues for any security concerns.

To give these permissions, add the following line to your sudoers file using `visudo`:
```
[USER] ALL=(ALL) NOPASSWD: /usr/bin/mount, /usr/bin/umount, /usr/bin/eject
```
Where `[USER]` is the user you want to give these permissions to.

# Dependencies
- Python 3 (Tested on 3.11)
  - pyquery
- MakeMKV
- ffmpeg
- cdparanoia
- abcde

These can be installed automatically on Ubuntu with the following command:
```sh
./ubuntu_install_dependencies.sh
```
Note that this will add the unofficial [MakeMKV PPA (ppa:heyarje/makemkv-beta)](https://launchpad.net/~heyarje/+archive/ubuntu/makemkv-beta) to your system.

# Usage

Blu-ray is not yet supported because I don't have a drive to develop with.

```
usage: rippa.py [-h] [--drive DRIVE] [--debug] [--wip-path WIP_PATH] [--dvd-path DVD_PATH] [--redbook-path REDBOOK_PATH] [--iso-path ISO_PATH] [--bluray-path BLURAY_PATH] [--skip-eject] [--makemkv-update-key] [--makemkv-settings-path MAKEMKV_SETTINGS_PATH]

options:
  -h, --help            show this help message and exit
  --drive DRIVE         Path to the optical drive (default: /dev/sr0)
  --debug               Enable debug logging (default: False)
  --wip-path WIP_PATH   Path to store work-in-progress files (default: ./wip)
  --dvd-path DVD_PATH   Path to rip dvd discs to (default: ./dvd)
  --redbook-path REDBOOK_PATH
                        Path to rip redbook audio discs to (default: ./redbook)
  --iso-path ISO_PATH   Path to rip data discs to (default: ./iso)
  --bluray-path BLURAY_PATH
                        Path to rip bluray discs to (default: ./bluray)
  --skip-eject          Don't eject the disc after ripping (default: False)
  --makemkv-update-key  Automatically update free MakeMKV key (default: False)
  --makemkv-settings-path MAKEMKV_SETTINGS_PATH
                        Path to the MakeMKV settings file (default: ~/.MakeMKV/settings.conf)
```
