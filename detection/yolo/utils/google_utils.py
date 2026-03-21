# -*- coding: utf-8 -*-
# Google utils: https://cloud.google.com/storage/docs/reference/libraries

import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

import requests
import torch


def gsutil_getsize(url=""):
    # gs://bucket/file size
    # https://cloud.google.com/storage/docs/gsutil/commands/du
    gsutil_cmd = shutil.which("gsutil")
    if not gsutil_cmd:
        raise FileNotFoundError("gsutil command not found in PATH")
    s = subprocess.check_output([gsutil_cmd, "du", url], shell=False).decode("utf-8")
    # Use int() instead of eval() for safety
    return int(s.split(" ")[0]) if s else 0  # bytes


def attempt_download(file, repo="WongKinYiu/yolov7"):
    # Attempt file download if does not exist
    file = Path(str(file).strip().replace("'", "").lower())

    if not file.exists():
        try:
            response = requests.get(
                f"https://api.github.com/repos/{repo}/releases/latest"
            ).json()  # github api
            assets = [x["name"] for x in response["assets"]]  # release assets
            tag = response["tag_name"]  # i.e. 'v1.0'
        except BaseException:  # fallback plan
            assets = [
                "yolov7.pt",
                "yolov7-tiny.pt",
                "yolov7x.pt",
                "yolov7-d6.pt",
                "yolov7-e6.pt",
                "yolov7-e6e.pt",
                "yolov7-w6.pt",
            ]
            tag = (
                subprocess.check_output(["git", "tag"], shell=False)
                .decode()
                .split()[-1]
            )

        name = file.name
        if name in assets:
            msg = f"{file} missing, try downloading from https://github.com/{repo}/releases/"
            redundant = False  # second download option
            try:  # GitHub
                url = f"https://github.com/{repo}/releases/download/{tag}/{name}"
                print(f"Downloading {url} to {file}...")
                torch.hub.download_url_to_file(url, file)
                if not (file.exists() and file.stat().st_size > 1e6):  # check
                    raise RuntimeError(f"Download failed or file too small: {file}")
            except Exception as e:  # GCP
                print(f"Download error: {e}")
                if not redundant:
                    raise RuntimeError("No secondary mirror")
                url = f"https://storage.googleapis.com/{repo}/ckpt/{name}"
                print(f"Downloading {url} to {file}...")
                curl_cmd = shutil.which("curl")
                if not curl_cmd:
                    raise FileNotFoundError("curl command not found in PATH")
                subprocess.run(
                    [curl_cmd, "-L", url, "-o", str(file)], shell=False, check=False
                )  # torch.hub.download_url_to_file(url, weights)
            finally:
                if not file.exists() or file.stat().st_size < 1e6:  # check
                    file.unlink(missing_ok=True)  # remove partial downloads
                    print(f"ERROR: Download failure: {msg}")
                print("")
                return


def gdrive_download(id="", file="tmp.zip"):
    # Downloads a file from Google Drive. from yolov7.utils.google_utils
    # import *; gdrive_download()
    curl_cmd = shutil.which("curl")
    if not curl_cmd:
        raise FileNotFoundError("curl command not found in PATH")
    unzip_cmd = shutil.which("unzip")
    if not unzip_cmd:
        raise FileNotFoundError("unzip command not found in PATH")

    t = time.time()
    file = Path(file)
    cookie = Path("cookie")  # gdrive cookie
    print(
        f"Downloading https://drive.google.com/uc?export=download&id={id} as {file}... ",
        end="",
    )
    file.unlink(missing_ok=True)  # remove existing file
    cookie.unlink(missing_ok=True)  # remove existing cookie

    # Attempt file download
    out = "NUL" if platform.system() == "Windows" else "/dev/null"
    with open(out, "w") as devnull:
        subprocess.run(
            [
                curl_cmd,
                "-c",
                "./cookie",
                "-s",
                "-L",
                f"drive.google.com/uc?export=download&id={id}",
            ],
            stdout=devnull,
            shell=False,
            check=False,
        )
    if os.path.exists("cookie"):  # large file
        token = get_token()
        result = subprocess.run(
            [
                curl_cmd,
                "-Lb",
                "./cookie",
                f"drive.google.com/uc?export=download&confirm={token}&id={id}",
                "-o",
                str(file),
            ],
            shell=False,
            check=False,
        )
    else:  # small file
        result = subprocess.run(
            [
                curl_cmd,
                "-s",
                "-L",
                "-o",
                str(file),
                f"drive.google.com/uc?export=download&id={id}",
            ],
            shell=False,
            check=False,
        )
    r = result.returncode  # execute, capture return
    cookie.unlink(missing_ok=True)  # remove existing cookie

    # Error check
    if r != 0:
        file.unlink(missing_ok=True)  # remove partial
        print("Download error ")  # raise Exception('Download error')
        return r

    # Unzip if archive
    if file.suffix == ".zip":
        print("unzipping... ", end="")
        subprocess.run([unzip_cmd, "-q", str(file)], shell=False, check=False)  # unzip
        file.unlink()  # remove zip to free space

    print(f"Done ({time.time() - t:.1f}s)")
    return r


def get_token(cookie="./cookie"):
    with open(cookie) as f:
        for line in f:
            if "download" in line:
                return line.split()[-1]
    return ""
