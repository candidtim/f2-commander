# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import mimetypes
import shutil
import subprocess
from pathlib import Path

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from ..config import config
from ..fs import breadth_first_walk


class Preview(Static):
    preview_path = reactive(Path.cwd(), recompose=True)

    def compose(self) -> ComposeResult:
        yield Static(self._format(self.preview_path))

    # FIXME: push_message (in)directy to the "other" panel?
    def on_other_panel_selected(self, path: Path):
        self.preview_path = path

    def watch_preview_path(self, old: Path, new: Path):
        parent: Widget = self.parent  # type: ignore
        parent.border_title = str(new)
        parent.border_subtitle = None

    def _format(self, path):
        if path is None:
            return ""
        elif path.is_dir():
            return self._dir_tree(path)
        elif path.is_file() and self._is_text(path):
            try:
                return Syntax(code=self._head(path), lexer=Syntax.guess_lexer(path))
            except UnicodeDecodeError:
                # file appears to be a binary file after all
                return "Cannot preview, not a text file"
        else:
            return "Cannot preview, not a text file"

    def _is_text(self, path) -> bool | None:
        """Attempt to detect if a file is a text file. Assume that the result may be
        wrong and the file may turn out to be binary.
        An altenrative implementation would use python-magic, but it creates a
        dependency on libmagic, which is not present on all systems."""
        try:
            mime_type = subprocess.check_output(
                ["file", "--brief", "--mime-type", path]
            ).decode("utf-8")
        except subprocess.SubprocessError:
            mime_type = mimetypes.guess_type(path)[0] or ""
        return mime_type.startswith("text/") if mime_type is not None else None

    @property
    def _height(self):
        """Viewport is not higher than this number of lines"""
        return shutil.get_terminal_size(fallback=(80, 200))[1]

    def _head(self, path):
        lines = []
        with open(path, "r") as f:
            try:
                for _ in range(self._height):
                    lines.append(next(f))
            except StopIteration:
                pass
        return "".join(lines)

    def _dir_tree(self, path):
        """To give a best possible overview of a directory, show it traversed
        breadth-first. Some directories may not be walked in a latter case, but
        top-level will be shown first, then the second level exapnded, and so on
        recursively as long as the output fits the screen."""

        # collect paths to show, breadth-first, but at most a screenful:
        collected_paths = []
        for i, p in enumerate(breadth_first_walk(path, config.show_hidden)):
            if i > self._height:
                break
            if p.parent in collected_paths:
                siblings = [e for e in collected_paths if e.parent == p.parent]  # :'(
                insert_at = collected_paths.index(p.parent) + len(siblings) + 1
                collected_paths.insert(insert_at, p)
            else:
                collected_paths.append(p)

        # format paths:
        lines = [str(path)]
        for p in collected_paths:
            name = str(p.relative_to(path))
            if p.is_dir():
                name += "/"
            lines.append(f"┣ {name}")
        return "\n".join(lines)
