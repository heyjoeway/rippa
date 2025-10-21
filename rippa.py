#!/usr/bin/env python3

import subprocess
from typing import Optional
import logging
import re
import time
import pathlib
import shutil
import os
import atexit
import threading
import json

from makemkvkey import updateMakeMkvKey


def log_subprocess_output(pipe):
    for line in iter(pipe.readline, b""):  # b'\n'-separated lines
        logging.debug("SUBPROCESS: %r", line.decode("utf-8"))


# Timeout is in seconds
def execute(cmd, capture=True, cwd=None) -> Optional[str]:
    if capture:
        return (
            subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.STDOUT)
            .strip()
            .decode("utf-8")
        )

    process = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    with process.stdout:
        log_subprocess_output(process.stdout)
    exitcode = process.wait()  # 0 means success
    if exitcode != 0:
        raise Exception(exitcode)

    return None


# Params are in format:
# A="B" C="D" E="F"
# Values CAN contain spaces, but they are always quoted
def parse_blkid_params(params_str: str) -> dict:
    params = {}
    for match in re.finditer(r'(\w+)="([^"]+)"', params_str):
        key = match.group(1)
        value = match.group(2)
        params[key] = value
    return params


def parse_blkid(blkid_str: str) -> dict:
    blkid = {}
    for line in blkid_str.split("\n"):
        if not line:
            continue
        parts = line.split(": ")
        blk = parts[0]
        params_str = parts[1]
        params = parse_blkid_params(params_str)
        blkid[blk] = params
    return blkid


# Returns a hash of the lengths of the tracks
def cdparanoia_hash(cdp_str: str) -> int:
    lines = cdp_str.split("\n")[6:-2]
    lengths = []
    for line in lines:
        split = line.split()
        if len(split) != 8:
            continue

        lengths.append(int(split[1]))
    return hash(tuple(lengths))


def trysudo(cmd: list[str]):
    try:
        execute(cmd, capture=False)
    except Exception as e:
        logging.debug("trysudo error: %s", e)
        logging.info("Retrying with sudo...")
        cmd = ["sudo"] + cmd
        execute(cmd, capture=False)


def eject(drive: str):
    trysudo(["eject", "-F", drive])


_mounts = []


def mount(drive: str, mnt_path: str):
    os.makedirs(mnt_path, exist_ok=True)
    trysudo(["mount", drive, mnt_path])
    _mounts.append(mnt_path)


def unmount(mnt_path: str):
    trysudo(["umount", mnt_path])


@atexit.register
def mount_cleanup():
    for mnt in _mounts:
        unmount(mnt)


class StoppableThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()


class LoopThread(StoppableThread):
    def __init__(self, interval=5):
        super().__init__()
        self._interval = interval

    def loop_step(self):
        pass

    def run(self):
        while not self.stopped():
            self.loop_step()
            time.sleep(self._interval)


class TranscodeThread(LoopThread):
    def __init__(
        self, wip_root: str, out_root: str, ffmpeg_args: Optional[list] = None
    ):
        super().__init__()
        self.wip_root = wip_root
        self.out_root = out_root

        if ffmpeg_args is None:
            ffmpeg_args = [
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-map",
                "0",
                "-c:a",
                "copy",
                "-c:s",
                "copy",
            ]
        self.ffmpeg_args = ffmpeg_args
        self.wip_dvd_root = f"{self.wip_root}/dvd"
        os.makedirs(self.wip_dvd_root, exist_ok=True)

    def _wait_for_file_stable(self, file_path: str, wait_time: int = 10):
        size1 = os.path.getsize(file_path)
        logging.debug(f"size1: {size1}")

        time.sleep(wait_time)  # Wait to see if the file size changes
        size2 = os.path.getsize(file_path)
        logging.debug(f"size2: {size2}")
        if size1 != size2:
            raise Exception(
                f"File {file_path} is not done being written "
                "(file size changed)"
            )

    def transcode_file(self, file_path: str, out_path: str):
        self._wait_for_file_stable(file_path)

        os.makedirs(out_path, exist_ok=True)

        file_name = os.path.basename(file_path)
        file_no_ext = os.path.splitext(file_name)[0]
        out_file_path = f"{out_path}/{file_no_ext}.mp4"

        cmd = (
            [
                "ffmpeg",
                "-i",
                file_path,
            ]
            + self.ffmpeg_args
            + [out_file_path]
        )
        logging.debug(f"Executing: {' '.join(cmd)}")
        execute(cmd, capture=False)

        logging.debug(f"Removing file: {file_path}")
        os.remove(file_path)

    def transcode_disc(self, disc_name: str):
        wip_dvd_root = f"{self.wip_root}/dvd"
        wip_transcode_dvd_root = f"{self.wip_root}/dvd_transcode"
        out_dvd_root = f"{self.out_root}/dvd"

        wip_path = f"{wip_dvd_root}/{disc_name}"
        wip_transcode_path = f"{wip_transcode_dvd_root}/{disc_name}"
        out_path = f"{out_dvd_root}/{disc_name}"

        wip_files = os.listdir(wip_path)
        logging.debug(f"wip_files: {wip_files}")

        for file in wip_files:
            raw_file_path = f"{wip_path}/{file}"
            transcode_file_path = f"{wip_transcode_path}/{file}"
            try:
                self.transcode_file(raw_file_path, wip_transcode_path)
                logging.info(f"Finished transcoding file: {file}")
            except Exception as e:
                logging.debug(f"transcode_file error: {e}")
                logging.debug("Maybe MakeMKV is still ripping the disc?")

        try:
            logging.debug(f"Removing wip_path: {wip_path}")
            os.rmdir(wip_path)
        except OSError:
            logging.debug(f"wip_path not empty, not removing: {wip_path}")

        wip_transcode_files = os.listdir(wip_transcode_path)
        logging.debug(f"wip_transcode_files: {wip_transcode_files}")

        os.makedirs(out_path, exist_ok=True)

        for file in wip_transcode_files:
            transcode_file_path = f"{wip_transcode_path}/{file}"
            self._wait_for_file_stable(transcode_file_path)
            shutil.move(transcode_file_path, out_path)
            logging.debug(f"Moved transcoded file to out: {file}")

        try:
            logging.debug(f"Removing wip_transcode_path: {wip_transcode_path}")
            os.rmdir(wip_transcode_path)
        except OSError:
            logging.debug(
                "wip_transcode_path not empty, not removing: "
                f"{wip_transcode_path}"
            )

    def loop_step(self):
        logging.debug("Transcode loop step")
        for disc_name in os.listdir(self.wip_dvd_root):
            logging.debug(f"Transcoding disc: {disc_name}")
            self.transcode_disc(disc_name)


class RipThread(LoopThread):
    def __init__(
        self,
        drive: str,
        wip_root: str,
        out_root: str,
        skip_eject: bool,
        makemkv_update_key: bool,
        makemkv_settings_path: Optional[str] = None,
    ):
        super().__init__()
        self.drive = drive
        self.wip_root = wip_root
        self.out_root = out_root
        self.skip_eject = skip_eject
        self.makemkv_update_key = makemkv_update_key
        self.makemkv_settings_path = makemkv_settings_path
        logging.debug("RipThread initialized")

    def rip_dvd(self, blkid_params: dict, drive: str):
        disc_name = f"{blkid_params['LABEL']}-{blkid_params['UUID']}"
        wip_rip_path = f"{self.wip_root}/dvd_rip/{disc_name}"
        wip_path = f"{self.wip_root}/dvd/{disc_name}"
        out_path = f"{self.out_root}/dvd/{disc_name}"

        if pathlib.Path(out_path).exists():
            logging.info(f"Output path exists: {out_path}")
            return

        if pathlib.Path(wip_path).exists():
            logging.info(f"WIP path exists: {wip_path}")
            return

        if self.makemkv_update_key:
            updateMakeMkvKey(self.makemkv_settings_path)

        logging.info(f"Ripping DVD: {disc_name}")

        shutil.rmtree(wip_rip_path, ignore_errors=True)
        os.makedirs(wip_rip_path, exist_ok=True)

        # Get number of the drive (eg. 0 for /dev/sr0, 1 for /dev/sr1, etc.)
        drive_id = int(re.search(r"\d+", self.drive).group(0))
        o_path_abs = os.path.abspath(wip_rip_path)

        cmd = [
            "makemkvcon",
            "mkv",
            f"disc:{drive_id}",
            "all",
            f"{o_path_abs}",
        ]
        logging.debug(f"Executing: {' '.join(cmd)}")
        execute(cmd, capture=False)

        os.makedirs(wip_path, exist_ok=True)
        # Move all files from the rip folder to the final wip folder,
        # then remove the rip folder
        for entry in os.listdir(wip_rip_path):
            src = os.path.join(wip_rip_path, entry)
            logging.debug(
                "Moving from rip path to wip path: "
                f"{src} -> {wip_path}"
            )
            shutil.move(src, wip_path)

        os.rmdir(wip_rip_path)

        # Transcoding is handled in its own thread, so we're done here!
        logging.info(f"Finished ripping DVD, wait for transcode: {disc_name}")

    def rip_redbook(self, cdp_str: str):
        cdp_hash = cdparanoia_hash(cdp_str)
        cdp_hash = str(hex(abs(cdp_hash)))[2:]

        # Check if any folders in out begin with the hash
        out_dir_path = f"{self.out_root}/redbook"
        os.makedirs(out_dir_path, exist_ok=True)
        for folder in os.listdir(out_dir_path):
            if folder.endswith(cdp_hash):
                logging.info(f"Redbook already ripped: {folder}")
                return

        logging.info(f"Ripping redbook: {cdp_hash}")

        wip_dir_path = f"{self.wip_root}/redbook"
        os.makedirs(wip_dir_path, exist_ok=True)

        pwd = os.getcwd()
        os.chdir(wip_dir_path)
        cmd = ["abcde", "-d", self.drive, "-o", "flac", "-B", "-N"]
        execute(cmd, capture=False)
        os.chdir(pwd)

        # Get name of first directory in wip folder
        album_name = os.listdir(wip_dir_path)[0]

        out_path = f"{out_dir_path}/{album_name}-{cdp_hash}"
        shutil.move(f"{wip_dir_path}/{album_name}", out_path)

        logging.info(f"Finished ripping redbook: {cdp_hash}")

    def rip_data_disc(self, blkid_params: dict):
        file_name = f"{blkid_params['LABEL']}-{blkid_params['UUID']}.iso"
        wip_dir_path = f"{self.wip_root}/iso"
        out_dir_path = f"{self.out_root}/iso"
        wip_path = f"{wip_dir_path}/{file_name}"
        out_path = f"{out_dir_path}/{file_name}"

        if pathlib.Path(out_path).exists():
            logging.info(f"Output path exists: {out_path}")
            return

        logging.info(f"Ripping data disc: {file_name}")

        os.makedirs(wip_dir_path, exist_ok=True)
        os.makedirs(out_dir_path, exist_ok=True)

        cmd = ["dd", f"if={self.drive}", f"of={wip_path}", "status=progress"]
        logging.debug(f"Executing: {' '.join(cmd)}")
        execute(cmd, capture=False, cwd=os.getcwd())

        # Move the file to the out folder
        shutil.move(wip_path, out_path)

        logging.info(f"Finished ripping data disc: {file_name}")

    def rip_bluray(blkid_params: dict):
        raise NotImplementedError("Blu-ray ripping is not yet implemented")

    def loop_step(self):
        logging.debug("Rip loop step")
        blkid_str = None
        try:
            blkid_str = execute(["blkid", self.drive], capture=True)
        except Exception as e:
            logging.debug("blkid error: %s", e)

        try:
            cdp_text = execute(["cdparanoia", "-sQ"], capture=True)
            logging.info("Redbook disc detected")
            self.rip_redbook(cdp_text)
            if not self.skip_eject:
                eject(self.drive)
            return
        except subprocess.CalledProcessError as e:
            logging.debug("cdparanoia error: %s", e)
            logging.debug("No redbook disc detected")

        if (blkid_str is None) or (len(blkid_str) == 0):
            logging.debug("No disc detected")
            return

        logging.debug(f"blkid_str: {blkid_str}")
        blkid_params = parse_blkid(blkid_str)[self.drive]
        logging.debug(f"params: {blkid_params}")

        mnt_path = f"./mnt{self.drive}"
        try:
            mount(self.drive, mnt_path)
        except Exception as e:
            logging.debug("mount error: %s", e)

        # Check if "VIDEO_TS" exists
        video_ts_path = f"{mnt_path}/VIDEO_TS"
        logging.debug(f"Checking for DVD at: {video_ts_path}")
        video_ts_exists = pathlib.Path(video_ts_path).exists()
        logging.debug(f"video_ts_exists: {video_ts_exists}")
        if video_ts_exists:
            logging.info("DVD detected")
            self.rip_dvd(blkid_params)
        else:
            logging.info("Data disc detected")
            self.rip_data_disc(blkid_params)

        if not self.skip_eject:
            eject(self.drive)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to the config file (see config.example.json)",
    )
    parser.add_argument(
        "--drive", default="/dev/sr0", help="Path to the optical drive"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--wip-root",
        default="./wip",
        help="Path to store work-in-progress files",
    )
    parser.add_argument(
        "--out-root", default="./out", help="Path to store finished files"
    )
    parser.add_argument(
        "--skip-eject",
        action="store_true",
        help="Don't eject the disc after ripping",
    )
    parser.add_argument(
        "--makemkv-update-key",
        action="store_true",
        help="Automatically update free MakeMKV key",
    )
    parser.add_argument(
        "--makemkv-settings-path",
        help="Path to the MakeMKV settings file",
        default="~/.MakeMKV/settings.conf",
    )
    args = parser.parse_args()

    if args.config:
        try:
            with open(args.config, "r") as f:
                config = json.load(f)
        except Exception as e:
            logging.warning(f"Error loading config file: {e}")
            config = {}
        parser.set_defaults(**config)
        args = parser.parse_args()
        # Add any data from the config file that wasn't in the command line
        for key, value in config.items():
            if not hasattr(args, key):
                setattr(args, key, value)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    transcode_thread = TranscodeThread(
        args.wip_root,
        args.out_root,
        getattr(args, "ffmpeg_args", None)
    )
    rip_thread = RipThread(
        args.drive,
        args.wip_root,
        args.out_root,
        args.skip_eject,
        args.makemkv_update_key,
        args.makemkv_settings_path,
    )

    transcode_thread.start()
    rip_thread.start()
    try:
        rip_thread.join()
    except KeyboardInterrupt:
        pass
    transcode_thread.stop()
    transcode_thread.join()
