# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

"""
Helper functions for fsspec file systems and their entries.

Does not use the Node abstraction on purpose, uses lower-level APIs only.
"""

import mimetypes
import os
import posixpath
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from fsspec import AbstractFileSystem
from PIL import Image as PillowImage
from send2trash import send2trash

TEXT_MIMETYPES = [
    # in addition to text/*, these are also considered to be text files:
    "application/json",
    "application/xml",
    "application/xml-dtd",
    "application/x-sh",
    "application/x-sql",
    "application/x-latex",
    "application/x-msdownload",  # .bat
    "message/rfc822",  # .eml
]

IMG_EXTENSIONS = {
    ext.lower()
    for ext in PillowImage.registered_extensions().keys()
    if ext.lower() != ".pdf"  # exclude PDF files from image preview
}


def find_mtime(info: dict[str, Any]) -> float:
    """Try to find the mtime in the stat returned by the fsspec file system
    implementation. Different implementations have different semantics for
    mtime, this implementation attempts all known keys and data types. If
    no mtime is found, it returns a default value of 1970-01-01 00:00:00."""

    # search for various mtime-like attributes:
    fs_mtime = None
    for name in (
        "mtime",
        "updated",
        "LastModified",
        "last_modified",
        "modify",
        "date_time",
    ):
        if name in info:
            fs_mtime = info[name]
            break

    mtime: Optional[float] = None

    # try to convert the value found:
    if isinstance(fs_mtime, str):
        try:
            mtime = datetime.fromisoformat(fs_mtime).timestamp()
        except ValueError:
            try:
                mtime = datetime.strptime(fs_mtime, "%Y%m%d%H%M%S").timestamp()
            except ValueError:
                pass
    elif isinstance(fs_mtime, datetime):
        mtime = fs_mtime.timestamp()
    elif isinstance(fs_mtime, tuple) and len(fs_mtime) == 6:
        mtime = datetime(*fs_mtime).timestamp()
    elif isinstance(fs_mtime, int):
        mtime = float(fs_mtime)
    elif isinstance(fs_mtime, float):
        mtime = fs_mtime

    # if could not find or convert, use a default value:
    if mtime is None:
        mtime = datetime(1970, 1, 1).timestamp()

    return mtime


def is_hidden(info: dict[str, Any]) -> bool:
    """Determine if the entry is hidden based on its name, stat, or native OS
    flags if it is in a local file system."""

    path = info["name"]
    return posixpath.basename(path).startswith(".") or _is_local_file_hidden(path)


def _is_local_file_hidden(path: str) -> bool:
    p = Path(path)
    if not p.exists():
        return False

    statinfo = p.lstat()
    return _has_hidden_attribute(statinfo) or _has_hidden_flag(statinfo)


def _has_hidden_attribute(statinfo: os.stat_result) -> bool:
    if not hasattr(statinfo, "st_file_attributes"):
        return False
    if not hasattr(stat, "FILE_ATTRIBUTE_HIDDEN"):
        return False
    return bool(statinfo.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)


def _has_hidden_flag(statinfo: os.stat_result) -> bool:
    if not hasattr(stat, "UF_HIDDEN") or not hasattr(statinfo, "st_flags"):
        return False
    return bool(statinfo.st_flags & stat.UF_HIDDEN)


def is_executable(statinfo: dict[str, Any]) -> bool:
    """Determine if the entry is executable based on its native OS mode,
    if available in the provided stat info."""

    if "mode" not in statinfo:
        return False

    mode = statinfo["mode"]
    return stat.S_ISREG(mode) and bool(mode & stat.S_IXUSR)


def is_text_file(path: str) -> bool:
    """Attempt to detect if a file is a text file.
    The result may be wrong and the file may turn out to be binary."""

    # NOTE: not using chardet to avoid opening all remote files for a test
    # (having said that, may use chardet in the local fs, and fallbak to the
    # mimetype check in the remote fs);
    # an altenrative implementation would use python-magic, but it creates a
    # dependency on libmagic, which may be not present in the OS.

    mime_type = None

    if Path(path).is_file():
        try:
            mime_type = subprocess.check_output(
                ["file", "-L", "--brief", "--mime-type", path]
            ).decode("utf-8")
        except subprocess.SubprocessError:
            pass

    if mime_type is None:
        mime_type = mimetypes.guess_type(path)[0]

    return mime_type is not None and (
        mime_type.startswith("text/")
        or mime_type.endswith("+xml")
        or mime_type.endswith("+json")
        or mime_type in TEXT_MIMETYPES
    )


def is_image_file(path: str) -> bool:
    _, ext = posixpath.splitext(path)
    return ext.lower() in IMG_EXTENSIONS


def is_pdf_file(path: str) -> bool:
    _, ext = posixpath.splitext(path)
    return ext.lower() == ".pdf"


def breadth_first_walk(
    fs: AbstractFileSystem, path: str, include_hidden: bool = True
) -> Iterator[str]:
    dirs_to_walk = [path]
    while dirs_to_walk:
        next_dirs_to_walk = []
        for d in dirs_to_walk:
            children = fs.ls(d, detail=True)
            ordered_by_name = sorted(children, key=lambda e: e["name"])
            for info in ordered_by_name:
                p = info["name"]
                if is_hidden(info) and not include_hidden:
                    continue
                if info.get("type") == "directory":
                    next_dirs_to_walk.append(p)
                yield p
        dirs_to_walk = next_dirs_to_walk


def copy_final_path(
    src: str,
    dst_fs: AbstractFileSystem,
    dst: str,
) -> str:
    """
    Compute actual final destination path for a given source,
    if it would be copied or moved to a given destination path.
    """
    return posixpath.join(dst, posixpath.basename(src)) if dst_fs.isdir(dst) else dst


def copy(src_fs: AbstractFileSystem, src: str, dst_fs: AbstractFileSystem, dst: str):
    """Copy file or directory in the same or between different file systems"""
    if src_fs == dst_fs:  # same file system (both local or both same remote)
        src_fs.copy(
            src,
            dst,
            recursive=src_fs.isdir(src),
            on_error="raise",
        )
    elif _is_local_fs(src_fs):  # upload to remote
        dst_fs.put(
            src,
            dst,
            recursive=src_fs.isdir(src),
            on_error="raise",
        )
    elif _is_local_fs(dst_fs):  # download from remote
        src_fs.get(
            src,
            dst,
            recursive=src_fs.isdir(src),
            on_error="raise",
        )
    else:  # distinct remote file systems: download and upload
        tmp_dir_path = tempfile.mkdtemp(prefix=f"{posixpath.basename(src)}.")
        try:
            src_fs.get(
                src,
                tmp_dir_path + "/",
                recursive=src_fs.isdir(src),
                on_error="raise",
            )
            dst_fs.put(
                posixpath.join(tmp_dir_path, os.path.basename(src)),
                dst,
                recursive=src_fs.isdir(src),
                on_error="raise",
            )
        finally:
            shutil.rmtree(tmp_dir_path)


def move(src_fs: AbstractFileSystem, src: str, dst_fs: AbstractFileSystem, dst: str):
    # Following code exists because fsspec may use strip_protocol on the path
    # removing the trailing slash and thus changing the semantics of `move`;
    # all would work as expected, except that non-existing target dir names
    # would not be used as the destination instead.
    if dst.endswith("/") and not dst_fs.isdir(dst):
        raise ValueError(f"No such directory: {dst}")

    if src_fs == dst_fs:  # same file system (both local or both same remote)
        src_fs.move(
            src,
            dst,
            recursive=src_fs.isdir(src),
            on_error="raise",
        )
    elif _is_local_fs(src_fs):  # upload to remote
        dst_fs.put(
            src,
            dst,
            recursive=src_fs.isdir(src),
            on_error="raise",
        )
        src_fs.rm(src, recursive=src_fs.isdir(src))
    elif _is_local_fs(dst_fs):  # download from remote
        src_fs.get(
            src,
            dst,
            recursive=src_fs.isdir(src),
            on_error="raise",
        )
        src_fs.rm(src, recursive=src_fs.isdir(src))
    else:  # distinct remote file systems: download and upload
        tmp_dir_path = tempfile.mkdtemp(prefix=f"{posixpath.basename(src)}.")
        try:
            src_fs.get(
                src,
                tmp_dir_path + "/",
                recursive=src_fs.isdir(src),
                on_error="raise",
            )
            dst_fs.put(
                posixpath.join(tmp_dir_path, os.path.basename(src)),
                dst,
                recursive=src_fs.isdir(src),
                on_error="raise",
            )
            src_fs.rm(src, recursive=src_fs.isdir(src))
        finally:
            shutil.rmtree(tmp_dir_path)


def rename(fs: AbstractFileSystem, path: str, new_name: str):
    new_path = posixpath.join(posixpath.dirname(path), new_name)
    if not fs.exists(new_path):
        fs.move(path, new_path)
    else:
        raise FileExistsError(f"File or directory already exists: {new_path}")


def delete(fs: AbstractFileSystem, path: str):
    if _is_local_fs(fs):
        send2trash(path)
    else:
        fs.rm(path, recursive=fs.isdir(path))


def mkdir(fs: AbstractFileSystem, path: str, new_name: str):
    new_path = posixpath.join(path, new_name)
    if not fs.exists(new_path):
        fs.makedirs(new_path)
    else:
        raise FileExistsError(f"File or directory already exists: {new_path}")


def mkfile(fs: AbstractFileSystem, path: str, new_name: str):
    new_path = posixpath.join(path, new_name)
    if not fs.exists(new_path):
        fs.touch(new_path)
    else:
        raise FileExistsError(f"File or directory already exists: {new_path}")


def _is_local_fs(fs: AbstractFileSystem) -> bool:
    return "file" in fs.protocol


def shorten(
    path: str,
    width_target: int,
    method: str = "truncate",
    unexpand_home: bool = True,
) -> str:
    """Shorten the path representation, guaranteed to fit the target width.
    Returned string obvioujlsy cannot be used as a path and may contain an ellipsis.
    Method 'truncate' adds an ellipsis at the end, 'slice' adds it in the middle."""

    assert method in ("truncate", "slice")

    placeholder = "..."

    if unexpand_home and Path(path).is_relative_to(Path.home()):
        path = str(Path("~") / Path(path).relative_to(Path.home()))

    # too/long/path -> too/long/...
    if len(path) > width_target and method == "truncate":
        cut_idx = width_target - len(placeholder)
        return path[:cut_idx] + placeholder

    # too/long/path -> too/.../path
    if len(path) > width_target and method == "slice":
        lead = "/" if path.startswith("/") else ""
        parts = path.split("/")
        short = path
        while len(short) > width_target - 1 and len(parts) > 3:
            mid = len(parts) // 2
            parts = parts[:mid] + parts[mid + 1 :]  # noqa (space before :)
            short = lead + posixpath.join(*parts[:mid], placeholder, *parts[mid:])
        if len(short) > width_target:  # if still too long, also truncate:
            short = shorten(short, width_target, method="truncate")
        return short

    return path
