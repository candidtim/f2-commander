# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import functools
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from humanize import naturalsize
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DataTable, Static
from textual.widgets.data_table import RowDoesNotExist

from f2.fs import DirEntry, DirList, list_dir

from ..commands import Command
from ..config import config_root
from ..shell import native_open
from .dialogs import InputDialog


class TextAndValue(Text):
    """Like `rich.text.Text`, but also holds a given `value`"""

    def __init__(self, value, text):
        self.value = value
        self.text = text

    def __getattr__(self, attr):
        return getattr(self.text, attr)


@dataclass
class SortOptions:
    key: str
    reverse: bool = False  # ascending by default, descending if True


class FileList(Static):
    BINDINGS_AND_COMMANDS = [
        Command(
            "order('name', False)",
            "Order by name, asc",
            "Order entries by name, from A to Z",
            "n",
        ),
        Command(
            "order('name', True)",
            "Order by name, desc",
            "Order entries by name, from Z to A",
            "N",
        ),
        Command(
            "order('size', False)",
            "Order by size, asc",
            "Order entries by size, smallest first",
            "s",
        ),
        Command(
            "order('size', True)",
            "Order by size, desc",
            "Order entries by size, largest first",
            "S",
        ),
        Command(
            "order('mtime', False)",
            "Order by mtime, asc",
            "Order entries by last modification time, oldest first",
            "t",
        ),
        Command(
            "order('mtime', True)",
            "Order by mtime, desc",
            "Order entries by last modification time, newest first",
            "T",
        ),
        Command(
            "find",
            "Find / filter with glob",
            "Filter files to show only those matching a glob",
            "f",
        ),
        Command(
            "open_in_os_file_manager",
            "Open in OS file manager",
            "Open current location in the default OS file manager",
            "o",
        ),
        Command(
            "navigate_to_config",
            "Show the configuration directory",
            "Open the user's configuration directory in the file list",
            "ctrl+g",
        ),
    ]
    BINDINGS = [
        Binding(cmd.binding_key, cmd.action, cmd.description, show=False)
        for cmd in BINDINGS_AND_COMMANDS
        if cmd.binding_key is not None
    ]

    COLUMN_PADDING = 2  # a column uses this many chars more to render
    SCROLLBAR_SIZE = 2
    TIME_FORMAT = "%b %d %H:%M"

    class Selected(Message):
        def __init__(self, path: Path, file_list: "FileList"):
            self.path = path
            self.file_list = file_list
            super().__init__()

        @property
        def contol(self) -> "FileList":
            return self.file_list

    path = reactive(Path.cwd())
    sort_options = reactive(SortOptions("name"))
    show_hidden = reactive(False)
    dirs_first = reactive(False)
    order_case_sensitive = reactive(False)
    cursor_path = reactive(Path.cwd())
    active = reactive(False)
    glob = reactive(None)
    selection: set[str] = set()

    def compose(self) -> ComposeResult:
        self.table: DataTable = DataTable(cursor_type="row")
        yield self.table

    def on_mount(self) -> None:
        # " ⬍" in "Name ⬍" will be removed after the initial sort
        self.table.add_column("Name ⬍", key="name")
        self.table.add_column("Size", key="size")
        self.table.add_column("Modified", key="mtime")

    def on_resize(self):
        self.update_listing()

    @property
    def current_path(self):
        pass

    def selected_paths(self) -> list[Path]:
        if len(self.selection) > 0:
            return list([self.path / name for name in self.selection])
        elif self.cursor_path.name != "..":
            return [self.cursor_path]
        else:
            return []  # FIXME: should be None

    def reset_selection(self):
        self.selection = set()

    def add_selection(self, name):
        if name == "..":
            return
        self.selection.add(name)

    def remove_selection(self, name):
        self.selection.remove(name)

    def toggle_selection(self, name):
        if name in self.selection:
            self.remove_selection(name)
        else:
            self.add_selection(name)

    #
    # FORMATTING:
    #

    def _row_style(self, e: DirEntry) -> str:
        # FIXME: use CSS instead
        style = ""

        if e.is_dir:
            style = "bold"
        elif e.is_executable:
            style = "#ab0000"
        elif e.is_hidden:
            style = "dim"
        elif e.is_link:
            style = "underline"

        if e.name in self.selection:
            style += " #fff04d italic"

        return style

    def _fmt_name(self, e: DirEntry, style: str) -> Text:
        text = Text()

        width_target = self._width_name()
        if not width_target:
            # container width is not known yet => assume smallest size, let the
            # container render once, then render the text on the next round
            return text

        # adjust width: cut long names
        if len(e.name) > width_target:
            suffix = "..."
            cut_idx = width_target - len(suffix)
            text.append(e.name[:cut_idx] + suffix, style=style)

        # FIXME: remove if textual supports full-width data tables
        # adjust width: pad short names to span the column
        else:
            pad_size = width_target - len(e.name)
            text.append(e.name, style=style)
            text.append(" " * pad_size)  # FIXME: the only reason to pass style as arg

        return text

    def _width_name(self):
        if self.size.width > 0:
            return (
                self.size.width
                - self._width_mtime()
                - self._width_size()
                - self.COLUMN_PADDING
                - self.SCROLLBAR_SIZE
            )
        else:
            return None

    def _fmt_size(self, e: DirEntry, style: str) -> Text:
        if e.name == "..":
            return Text("-- UP⇧ --", style=style, justify="center")
        elif e.is_dir:
            return Text("-- DIR --", style=style, justify="center")
        elif e.is_link:
            return Text("-- LNK --", style=style, justify="center")
        else:
            return Text(naturalsize(e.size), style=style, justify="right")

    @functools.cache
    def _width_size(self):
        return len(naturalsize(123)) + self.COLUMN_PADDING

    def _fmt_mtime(self, e: DirEntry, style: str) -> Text:
        return Text(
            time.strftime(self.TIME_FORMAT, time.localtime(e.mtime)),
            style=style,
        )

    @functools.cache
    def _width_mtime(self):
        return len(time.strftime(self.TIME_FORMAT)) + self.COLUMN_PADDING

    #
    # END OF FORMATTING
    #
    # ORDERING:
    #

    def sort_key(self, name_and_value):
        sort_key_fn = {
            "name": self.sort_key_by_name,
            "size": self.sort_key_by_size,
            "mtime": self.sort_key_by_mtime,
        }[self.sort_options.key]
        entry: DirEntry = name_and_value.value
        return sort_key_fn(entry)

    def sort_key_by_name(self, e: DirEntry) -> str:
        # stick ".." at the top of the list, regardless of the order (asc/desc)
        if e.name == "..":
            return "\u0000" if not self.sort_options.reverse else "\uFFFF"

        # dirs first, if asked for
        prefix = ""
        if self.dirs_first and e.is_dir:
            prefix = "\u0001" if not self.sort_options.reverse else "\uFFFE"

        # handle case sensetivity
        name = e.name
        if not self.order_case_sensitive:
            name = name.lower() + name  # keeping original name for stable ordering

        return prefix + name

    def sort_key_by_size(self, e: DirEntry) -> Tuple[int, str | None]:
        max_file_size = 2**64  # maximum file size in zfs, and probably on the planet
        # stick ".." at the top of the list, regardless of the order (asc/desc)
        if e.name == "..":
            size_key = -1 if not self.sort_options.reverse else max_file_size + 1
            return (size_key, None)

        size_key = e.size
        # when ordering by size, dirs are always first
        if e.is_dir or e.is_link:
            size_key = 0 if not self.sort_options.reverse else max_file_size

        return (size_key, self.sort_key_by_name(e))  # add name for stable ordering

    def sort_key_by_mtime(self, e: DirEntry) -> Tuple[float, str | None]:
        y3k = 32_503_680_000  # this program has Y3K issues
        # stick ".." at the top of the list, regardless of the order (asc/desc)
        if e.name == "..":
            key = -1 if not self.sort_options.reverse else 2 * y3k
            return (key, None)

        mtime_key = e.mtime
        if self.dirs_first:
            if not self.sort_options.reverse and not e.is_dir:
                mtime_key = e.mtime + y3k
            elif self.sort_options.reverse and e.is_dir:
                mtime_key = e.mtime + y3k

        return (mtime_key, self.sort_key_by_name(e))  # add name for stable ordering

    #
    # END OF ORDERING
    #

    def _update_table(self, ls: DirList):
        self.table.clear()
        for child in ls.entries:
            style = self._row_style(child)
            self.table.add_row(
                # name column also holds original values:
                TextAndValue(child, self._fmt_name(child, style)),
                self._fmt_size(child, style),
                self._fmt_mtime(child, style),
                key=child.name,
            )
        self.table.sort("name", key=self.sort_key, reverse=self.sort_options.reverse)

    def update_listing(self):
        old_cursor_path = self.cursor_path
        ls = list_dir(
            self.path, include_hidden=self.show_hidden, glob_expression=self.glob
        )
        self._update_table(ls)
        # if still in the same dir, try to locate the previous cursor position
        if old_cursor_path.parent == self.path:
            try:
                idx = self.table.get_row_index(old_cursor_path.name)
                self.table.cursor_coordinate = (idx, 0)  # type: ignore
            except RowDoesNotExist:
                pass
        # update list border with some information about the directory:
        total_size_str = naturalsize(ls.total_size)
        self.parent.border_title = str(self.path)
        subtitle = f"{total_size_str} in {ls.file_count} files | {ls.dir_count} dirs"
        if self.glob is not None:
            subtitle = f"[red]{self.glob}[/red] | {subtitle}"
        self.parent.border_subtitle = subtitle

    def watch_path(self, old_path: Path, new_path: Path):
        self.reset_selection()
        self.glob = None
        self.update_listing()
        # if navigated "up", select source dir in the new list:
        if new_path == old_path.parent:
            try:
                idx = self.table.get_row_index(old_path.name)
                self.table.cursor_coordinate = (idx, 0)  # type: ignore
            except RowDoesNotExist:
                pass

    def watch_show_hidden(self, old: bool, new: bool):
        if not new:  # if some files will be not shown anymore, better be safe:
            self.reset_selection()
        self.update_listing()

    def watch_dirs_first(self, old: bool, new: bool):
        self.update_listing()

    def watch_order_case_sensitive(self, old: bool, new: bool):
        self.update_listing()

    def watch_sort_options(self, old: SortOptions, new: SortOptions):
        self.update_listing()
        # remove sort label from the previously sorted column:
        prev_sort_col = self.table.columns[old.key]  # type: ignore
        prev_sort_col.label = prev_sort_col.label[:-2]
        # add the new sort label:
        new_sort_col = self.table.columns[new.key]  # type: ignore
        direction = "⬆" if new.reverse else "⬇"
        new_sort_col.label = f"{new_sort_col.label} {direction}"  # type: ignore

    def watch_glob(self, old: str | None, new: str | None):
        self.reset_selection()
        self.update_listing()

    # FIXME: refactor (simplify) ordering logic; see if DataTable provides better API
    def action_order(self, key: str, reverse: bool):
        # if the user chooses the same order again, reverse it:
        # (e.g., pressing `n` twice will reverse the order the second time)
        new_sort_options = SortOptions(key, reverse)
        if self.sort_options == new_sort_options:
            new_sort_options = SortOptions(key, not reverse)
        self.sort_options = new_sort_options

    def action_find(self):
        def on_find(value):
            if value.strip() == "" or value.strip() == "*":
                self.glob = None
            else:
                self.glob = value

        self.app.push_screen(
            InputDialog(
                title="Find files, enter glob expression",
                value=self.glob or "*",
                btn_ok="Find",
            ),
            on_find,
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        entry_name: str = event.row_key.value  # type: ignore
        selected_path = (self.path / entry_name).resolve()
        if selected_path.is_dir():
            self.path = selected_path

    def action_open(self):
        if self.cursor_path.is_dir():
            pass  # already handled by on_data_table_row_selected
        elif self.cursor_path.is_file() and os.access(self.cursor_path, os.X_OK):
            # TODO: ask to confirm to run, let chose mode (on a side or in a shell)
            pass
        else:
            open_cmd = native_open()
            if open_cmd is not None:
                with self.app.suspend():
                    subprocess.run(open_cmd + [str(self.cursor_path)])

    def action_open_in_os_file_manager(self):
        open_cmd = native_open()
        if open_cmd is not None:
            with self.app.suspend():
                subprocess.run(open_cmd + [str(self.path)])

    def action_navigate_to_config(self):
        self.path = config_root()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        self.cursor_path = self.path / event.row_key.value  # type: ignore
        self.post_message(self.Selected(path=self.cursor_path, file_list=self))

    def on_descendant_focus(self):
        self.active = True
        self.add_class("focused")

    def on_descendant_blur(self):
        self.active = False
        self.remove_class("focused")

    def on_key(self, event: events.Key) -> None:
        # FIXME: refactor to use actions?
        # FIXME: shouldn't j/k work out of the box with DataTable?
        if event.key == "j":
            new_coord = (self.table.cursor_coordinate[0] + 1, 0)
            self.table.cursor_coordinate = new_coord  # type: ignore
        elif event.key == "k":
            new_coord = (self.table.cursor_coordinate[0] - 1, 0)
            self.table.cursor_coordinate = new_coord  # type: ignore
        elif event.key == "g":
            self.table.action_scroll_top()
        elif event.key == "G":
            self.table.action_scroll_bottom()
        elif event.key in ("ctrl+f", "ctrl+d"):
            self.table.action_page_down()
        elif event.key in ("ctrl+b", "ctrl+u"):
            self.table.action_page_up()
        elif event.key == "b":
            self.path = self.path.parent
        elif event.key == "backspace":
            self.path = self.path.parent
        elif event.key == "R":
            self.update_listing()
        elif event.key == "enter":
            self.action_open()
        elif event.key == "space":
            self.toggle_selection(self.cursor_path.name)
            self.update_listing()
            new_coord = (self.table.cursor_coordinate[0] + 1, 0)
            self.table.cursor_coordinate = new_coord  # type: ignore
        elif event.key == "minus":
            self.reset_selection()
            self.update_listing()
        elif event.key == "plus":
            for key in self.table.rows:
                self.add_selection(key.value)
            self.update_listing()
        elif event.key == "asterisk":
            for key in self.table.rows:
                self.toggle_selection(key.value)
            self.update_listing()
