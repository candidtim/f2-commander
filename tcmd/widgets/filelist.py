import functools
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from humanize import naturalsize
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DataTable, Static
from textual.widgets.data_table import RowDoesNotExist

from tcmd.fs import DirEntry, DirList, list_dir

from ..shell import native_open
from .dialogs import InputDialog


@functools.total_ordering
class Sortable(Text):
    """Like rich.text.Text, but with ordering based on a raw value"""

    def __init__(self, value, *args, **kwargs):
        self.value = value
        super().__init__(*args, **kwargs)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Sortable):
            return NotImplemented
        return self.value < other.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Sortable):
            return NotImplemented
        return self.value == other.value


@dataclass
class SortOptions:
    key: str
    reverse: bool = False  # ascending by default, descending if True


class FileList(Static):
    BINDINGS = [
        Binding("n", "order('name', False)", "Order by name (asc)", show=False),
        Binding("N", "order('name', True)", "Order by name (desc)", show=False),
        Binding("s", "order('size', False)", "Order by size (asc)", show=False),
        Binding("S", "order('size', True)", "Order by size (desc)", show=False),
        Binding(
            "t",
            "order('mtime', False)",
            "Order by last modified time (asc)",
            show=False,
        ),
        Binding(
            "T",
            "order('mtime', True)",
            "Order by last modified time (desc)",
            show=False,
        ),
        Binding("f", "find", "Find files using glob expressions", show=False),
    ]

    COLUMN_PADDING = 2  # a column uses this many chars more to render
    SCROLLBAR_SIZE = 2  # TODO: only apply when showing a vertical scrollbar
    TIME_FORMAT = "%b %d %H:%M"

    class Selected(Message):
        def __init__(self, path: Path, file_list: "FileList"):
            self.path = path
            self.file_list = file_list
            super().__init__()

        @property
        def control(self) -> "FileList":
            return self.file_list

    path = reactive(Path.cwd())
    sort_options = reactive(SortOptions("name"))
    show_hidden = reactive(True)
    # TODO: disallow ".." as current_path
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
            # TODO: handle empty result better in app.py
            return []

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

    def _row_style(self, e: DirEntry) -> str:
        # FIXME: can the Textual CSS or its standard colors be used here?
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

    def _fmt_name(self, e: DirEntry, style: str, reverse_sort: bool) -> Text:
        sort_key = e.name
        if e.name == "..":
            # stick ".." at the top of the list
            sort_key = "\u0000" if not reverse_sort else "\uFFFF"
        text = Sortable(sort_key)

        # adjust width
        name = e.name
        width_target = self._width_name()
        if width_target and len(e.name) > width_target:
            suffix = "..."
            cut_idx = width_target - len(suffix)
            text.append(name[:cut_idx] + suffix)
        elif width_target and len(e.name) <= width_target:
            pad_size = width_target - len(e.name)
            text.append(name, style=style)
            text.append(" " * pad_size)
        else:
            # do not add any text if the container width is not known yet
            # -> assume smallest container size, render on next round
            pass

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

    def _fmt_size(self, e: DirEntry, style: str, reverse_sort: bool) -> Text:
        sort_key = (e.size, e.name)  # sort by size, then by name
        if e.name == "..":
            # stick ".." at the top of the list
            # 2 ^ 64 is a max file size in zfs
            sort_key = (-100 if not reverse_sort else 2**64 + 100, e.name)
            return Sortable(
                sort_key,
                "-- UP⇧ --",
                style=style,
                justify="center",
            )
        elif e.is_dir:
            # show dirs and links at the top of the list
            sort_key = (-50 if not reverse_sort else 2**64 + 50, e.name)
            return Sortable(
                sort_key,
                "-- DIR --",
                style=style,
                justify="center",
            )
        elif e.is_link:
            # show dirs and links at the top of the list
            sort_key = (-50 if not reverse_sort else 2**64 + 50, e.name)
            return Sortable(
                sort_key,
                "-- LNK --",
                style=style,
                justify="center",
            )
        else:
            return Sortable(
                (e.size, e.name),  # files after dirs and links
                naturalsize(e.size),
                style=style,
                justify="right",
            )

    @functools.cache
    def _width_size(self):
        return len(naturalsize(123)) + self.COLUMN_PADDING

    def _fmt_mtime(self, e: DirEntry, style: str, reverse_sort: bool) -> Text:
        sort_key = e.mtime
        if e.name == "..":
            # stick ".." at the top of the list
            sort_key = -1 if not reverse_sort else 32503680000  # Y3K problem
        return Sortable(
            sort_key,
            time.strftime(self.TIME_FORMAT, time.localtime(e.mtime)),
            style=style,
        )

    @functools.cache
    def _width_mtime(self):
        return len(time.strftime(self.TIME_FORMAT)) + self.COLUMN_PADDING

    def _update_table(self, ls: DirList, sort_options: SortOptions):
        self.table.clear()
        for child in ls.entries:
            style = self._row_style(child)
            self.table.add_row(
                self._fmt_name(child, style, sort_options.reverse),
                self._fmt_size(child, style, sort_options.reverse),
                self._fmt_mtime(child, style, sort_options.reverse),
                key=child.name,
            )
        self.table.sort(sort_options.key, reverse=sort_options.reverse)

    def update_listing(self):
        old_cursor_path = self.cursor_path
        ls = list_dir(
            self.path, include_hidden=self.show_hidden, glob_expression=self.glob
        )
        self._update_table(ls, self.sort_options)
        # if still in the same dir, try to locate the previous cursor position
        if old_cursor_path.parent == self.path:
            try:
                idx = self.table.get_row_index(old_cursor_path.name)
                self.table.cursor_coordinate = (idx, 0)  # type: ignore
            except RowDoesNotExist:
                pass
        # update list border with some information about the directory:
        total_size_str = naturalsize(ls.total_size)
        self.border_title = str(self.path)
        subtitle = f"{total_size_str} in {ls.file_count} files | {ls.dir_count} dirs"
        if self.glob is not None:
            subtitle = f"[red]{self.glob}[/red] | {subtitle}"
        self.border_subtitle = subtitle

    def watch_path(self, old_path: Path, new_path: Path):
        self.reset_selection()
        self.update_listing()
        # if navigated "up", select source dir in the new list:
        if new_path == old_path.parent:
            try:
                idx = self.table.get_row_index(old_path.name)
                self.table.cursor_coordinate = (idx, 0)  # type: ignore
            except RowDoesNotExist:
                pass

    def watch_show_hidden(self, old: bool, new: bool):
        # TODO: check if there where any hidden files selected and let user choose?
        if not new:  # if some files will be not shown anymore, better be safe:
            self.reset_selection()
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

    # TODO: refactor all ordering logic, see if DataTable provides better API
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
        selected_path = (self.path / event.row_key.value).resolve()
        if selected_path.is_dir():
            # TODO: when following links, keep track of actual "previous" dir
            self.path = selected_path
        else:
            self.open_native(selected_path)

    def open_native(self, path):
        open_cmd = native_open()
        if open_cmd is not None:
            with self.app.suspend():
                subprocess.run(open_cmd + [str(path)])

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
        # FIXME: shouldn't DataTable default bindings do the same?
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
        # TODO: have u/d scroll half of a page
        elif event.key in ("ctrl+f", "ctrl+d"):
            self.table.action_page_down()
        elif event.key in ("ctrl+b", "ctrl+u"):
            self.table.action_page_up()
        # FIXME: refactor to use actions?
        elif event.key == "b":
            self.path = self.path.parent
        elif event.key == "backspace":
            self.path = self.path.parent
        elif event.key == "R":
            self.update_listing()
        elif event.key == "space":
            key = self.cursor_path.name
            self.toggle_selection(key)
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
