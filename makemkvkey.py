#!/usr/bin/env python3

from pyquery import PyQuery as pq
import re
import os

MAKEMKV_KEY_URL = "https://forum.makemkv.com/forum/viewtopic.php?t=1053"


def getMakeMkvKey():
    pqSite = pq(url=MAKEMKV_KEY_URL)
    pqCodeBlock = pqSite("#post_content3548 > .content code")
    return pqCodeBlock.text()


def updateMakeMkvKey(settingsPath: str):
    key = getMakeMkvKey()

    settingsPath = os.path.expanduser(settingsPath)

    with open(settingsPath, "r") as settingsFile:
        settings = settingsFile.read()

    # Find line beginning with "app_Key =" and ending with ";"
    # Replace the key in the line
    # If the line is not found, append the key to the end of the file
    settings = re.sub(r"app_Key = \".*\";", f'app_Key = "{key}";', settings)

    with open(settingsPath, "w") as settingsFile:
        settingsFile.write(settings)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Update MakeMKV key")
    parser.add_argument(
        "--print-only",
        help="Print the key to the console",
        action="store_true",
    )
    parser.add_argument(
        "--settings-path",
        help="Path to the MakeMKV settings file",
        default="~/.MakeMKV/settings.conf",
    )

    args = parser.parse_args()

    if args.print_only:
        print(getMakeMkvKey())
    else:
        updateMakeMkvKey(args.settings_path)


if __name__ == "__main__":
    main()
