# Rippa

> **Step 1:** Insert disc
>
> **Step 2:** Wait
>
> **Step 3:** ?????
>
> **Step 4:** Profit

Automatically rip discs (Data, Audio, DVD) when inserted. Data discs get ripped to ISO. Audio CDs get transcoded to FLAC. DVDs are ripped by MakeMKV, then transcoded to H264 MP4s in parallel. Blu-ray is not yet supported because I don't have a drive to develop with.

# TrueNAS Scale App (Recommended)

Create a new custom TrueNAS Scale App (Apps > Discover Apps > Custom App) with the following settings:

- **Application Name:** `Rippa`
- **Image Configuration**
  - Repository: `heyjoeway/rippa`
- **Container Configuration**
  - Hostname: `rippa`
  - Restart Policy: `Unless Stopped`
- **Devices**
  -	Add:
    -	Host Device: `/dev/sr0`
    -	Container Device: `/dev/sr0`
- **Security Context Configuration**
  -	Privileged: Yes
- **Storage Configuration**
  -	Entry 1:
    -	Type: `Host Path`
    -	Mount Path: `/app/out/iso`
    -	Host Path: `[Path to output ISO files on TrueNAS]`
  -	Entry 2:
    -	Type: `Host Path`
    -	Mount Path: `/app/out/redbook`
    -	Host Path: `[Path to output audio rips on TrueNAS]`
  -	Entry 3:
    -	Type: `Host Path`
    -	Mount Path: `/app/out/dvd`
    -	Host Path: `[Path to output DVD rips on TrueNAS]`


# Docker Quick Start (Recommended)

[You will need a working Docker installation.](https://docs.docker.com/engine/install/)

## Security Notice

To access the optical drive device and mount filesystems, the Docker container requires privileged access. [Official documentation on the risks can be read at this link.](https://docs.docker.com/engine/containers/run/#runtime-privilege-and-linux-capabilities) As a mitigaton, you can add `--network none` to any of the `docker run` commands to block all network access, but doing so will prevent audio CD rips from being automatically tagged. Any pull requests to handle this more securely are welcome.

## Starting the Container

Make sure to replace the paths in `[BRACKETS]` with your desired paths.

```sh
# If you previously ran the container
docker stop rippa
docker rm rippa

docker run \
  --name rippa \
  --device=/dev/sr0:/dev/sr0 \
  -v [PATH TO WIP FILES]:/app/wip \
  -v [PATH TO OUTPUT ISO RIPS]:/app/out/iso \
  -v [PATH TO OUTPUT AUDIO RIPS]:/app/out/redbook \
  -v [PATH TO OUTPUT DVD RIPS]:/app/out/dvd \
  --restart unless-stopped \
  --detach \
  --privileged \
  heyjoeway/rippa:latest
```

# Docker Development

**This is for doing development in Docker only. Please see the previous section if you just want to run Rippa.**

In the directory containing the `Dockerfile`, run the following commands:

```sh
# Build
docker build -t rippa:latest .

# Run with device access
# Replace /dev/sr0 with your optical drive device if different
# (it's almost never different)
# Working directory + ./app is mounted to /app in the container
docker run --rm -it \
  --device=/dev/sr0:/dev/sr0 \
  -v "$(pwd)/app":/app \
  --privileged \
  rippa:latest
```

# Running directly

## Security Notice

This script is meant to be run as an unprivileged user, but does require superuser rights for mounting and ejecting discs. I do not claim to know the full risk of doing this in terms of security and it is up to the user to ensure their environment is safe to allow this in. Please open issues for any security concerns.

To give these permissions, add the following line to your sudoers file using `visudo`:
```
[USER] ALL=(ALL) NOPASSWD: /usr/bin/mount, /usr/bin/umount, /usr/bin/eject
```
Where `[USER]` is the user you want to give these permissions to.

## Dependencies
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

## CLI Help

```
usage: rippa.py [-h] [--config CONFIG] [--drive DRIVE] [--debug] [--wip-root WIP_ROOT] [--out-root OUT_ROOT] [--skip-eject] [--makemkv-update-key] [--makemkv-settings-path MAKEMKV_SETTINGS_PATH]

options:
  -h, --help            show this help message and exit
  --config CONFIG       Path to the config file (see config.example.json) (default: config.json)
  --drive DRIVE         Path to the optical drive (default: /dev/sr0)
  --debug               Enable debug logging (default: False)
  --wip-root WIP_ROOT   Path to store work-in-progress files (default: ./wip)
  --out-root OUT_ROOT   Path to store finished files (default: ./out)
  --skip-eject          Don't eject the disc after ripping (default: False)
  --makemkv-update-key  Automatically update free MakeMKV key (default: False)
  --makemkv-settings-path MAKEMKV_SETTINGS_PATH
                        Path to the MakeMKV settings file (default: ~/.MakeMKV/settings.conf)
```
