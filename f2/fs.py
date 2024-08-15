# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import fnmatch
import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DirList:
    file_count: int
    dir_count: int
    total_size: int
    entries: list["DirEntry"]


@dataclass
class DirEntry:
    name: str
    size: int
    mtime: float
    is_file: bool
    is_dir: bool
    is_link: bool
    is_hidden: bool
    is_executable: bool

    @classmethod
    def from_path(cls, p: Path) -> "DirEntry":
        statinfo = p.lstat()
        return DirEntry(
            name=p.name,
            size=statinfo.st_size,
            mtime=statinfo.st_mtime,
            is_file=stat.S_ISREG(statinfo.st_mode),
            is_dir=stat.S_ISDIR(statinfo.st_mode),
            is_link=stat.S_ISLNK(statinfo.st_mode),
            is_hidden=is_hidden(p, statinfo),
            is_executable=is_executable(statinfo),
        )


def has_hidden_attribute(statinfo: os.stat_result) -> bool:
    if not hasattr(statinfo, "st_file_attributes"):
        return False
    if not hasattr(stat, "FILE_ATTRIBUTE_HIDDEN"):
        return False
    return bool(
        statinfo.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN  # type: ignore
    )


def has_hidden_flag(statinfo: os.stat_result) -> bool:
    if not hasattr(stat, "UF_HIDDEN") or not hasattr(statinfo, "st_flags"):
        return False
    return bool(statinfo.st_flags & stat.UF_HIDDEN)  # type: ignore


def is_hidden(path: Path, statinfo: os.stat_result) -> bool:
    return (
        path.name.startswith(".")
        or has_hidden_attribute(statinfo)
        or has_hidden_flag(statinfo)
    )


def is_executable(statinfo: os.stat_result) -> bool:
    mode = statinfo.st_mode
    return stat.S_ISREG(mode) and bool(mode & stat.S_IXUSR)


def list_dir(
    path: Path,
    include_up_dir: bool = True,
    include_hidden: bool = True,
    glob_expression: str | None = None,
) -> DirList:
    if not path.is_dir():
        raise ValueError(f"{path} is not a directory")

    total_size = 0
    file_count = 0
    dir_count = 0
    entries = []

    if include_up_dir and path.parent != path:
        up = DirEntry.from_path(path)
        up.name = ".."
        entries.append(up)

    for child in path.iterdir():
        entry = DirEntry.from_path(child)
        if glob_expression and not fnmatch.fnmatch(entry.name, glob_expression):
            continue
        if entry.is_hidden and not include_hidden:
            continue
        entries.append(entry)
        total_size += entry.size
        if entry.is_file:
            file_count += 1
        elif entry.is_dir:
            dir_count += 1

    return DirList(
        file_count=file_count,
        dir_count=dir_count,
        total_size=total_size,
        entries=entries,
    )
