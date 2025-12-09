# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import posixpath
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fsspec import AbstractFileSystem
from fsspec.core import url_to_fs

from .arch import is_archive
from .util import find_mtime, is_executable, is_hidden


@dataclass(frozen=True)
class Node:
    """Immutable eager-loaded representation of a file system node"""

    # identity:
    fs: AbstractFileSystem
    path: str

    # attributes:
    name: str
    size: int
    mtime: float
    is_file: bool
    is_dir: bool
    is_link: bool
    is_hidden: bool
    is_executable: bool
    is_archive: bool
    is_local: bool

    # additional properties:
    _parent: Optional["Node"] = None

    @classmethod
    def from_url(cls, url: str) -> "Node":
        try:
            fs, path = url_to_fs(url)
        except Exception as e:
            raise ValueError(f"Invalid URL: {url}") from e
        else:
            return Node.from_path(fs, path)

    @classmethod
    def from_path(
        cls,
        fs: AbstractFileSystem,
        path: str,
        stat: Optional[dict] = None,
        parent: Optional["Node"] = None,
    ) -> "Node":
        if stat is None:
            stat = fs.stat(path)

        name = stat["name"]
        type_ = stat["type"]
        size = int(stat.get("size") or 0)  # that's correct: get() or 0, for adlfs
        return cls(
            fs=fs,
            path=path,
            name=posixpath.basename(name),
            size=size,
            mtime=find_mtime(stat),
            # NOTE: links may have type == "other"
            is_dir=type_ == "directory" or (type_ == "other" and fs.isdir(path)),
            is_file=type_ == "file" or (type_ == "other" and fs.isfile(path)),
            is_link=stat.get("islink", False),
            is_hidden=is_hidden(stat),
            is_executable=is_executable(stat),
            is_archive=is_archive(path),
            is_local="file" in fs.protocol,
            _parent=parent,
        )

    @classmethod
    def cwd(cls) -> "Node":
        return cls.from_url(Path.cwd().as_uri())

    @property
    def parent(self) -> Optional["Node"]:
        # if parent node was explicitly provided, return it:
        if self._parent is not None:
            return self._parent

        # otherwise, locate it in the file system as usual:
        parent_path = posixpath.dirname(self.path)
        return (
            Node.from_path(self.fs, parent_path) if parent_path != self.path else None
        )

    @property
    def basename(self) -> str:
        """
        Node name extracted from its path. Can be different from the value in the `name`
        attribute, which can be assigned a different display name.
        """
        return posixpath.basename(self.path)

    def list(self) -> list["Node"]:
        if not self.is_dir:
            raise ValueError(f"Node is not a directory: {self}")

        return [
            Node.from_path(
                self.fs,
                posixpath.join(self.path, posixpath.basename(stat["name"])),
                stat,
                parent=self,
            )
            for stat in self.fs.ls(self.path, detail=True)
        ]

    def __str__(self) -> str:
        return self.fs.unstrip_protocol(self.path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return False
        return self.fs == other.fs and self.path == other.path
