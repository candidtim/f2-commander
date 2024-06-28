import functools
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
    # TODO: reflect selection in the panel footer (should be reactive then?)
    # TODO: disallow ".." in selection
    selection: set[str] = set()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        # TODO: force redraw / recompute dimensions after chaning dir
        # TODO: cut too long file names and add ...
        # TODO: also make to short file names appear wider then?
        self.table: DataTable = DataTable(cursor_type="row")
        yield self.table

    def on_mount(self) -> None:
        # TODO: use full width of the parent container
        # " ⬍" in "Name ⬍" will be removed after the initial sort
        self.table.add_column("Name ⬍", key="name")
        self.table.add_column("Size", key="size")
        self.table.add_column("Modified", key="mtime")

    def selected_paths(self) -> list[Path]:
        if len(self.selection) > 0:
            return list([self.path / name for name in self.selection])
        else:
            return [self.cursor_path]

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

        # TODO: also make the selection stand out when under cursor
        if e.name in self.selection:
            style += " #fff04d"

        return style

    def _fmt_name(self, e: DirEntry, style: str, reverse_sort: bool) -> Text:
        sort_key = e.name
        if e.name == "..":
            # stick ".." at the top of the list
            sort_key = "\u0000" if not reverse_sort else "\uFFFF"
        return Sortable(sort_key, e.name, style=style)

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

    def _fmt_mtime(self, e: DirEntry, style: str, reverse_sort: bool) -> Text:
        sort_key = e.mtime
        if e.name == "..":
            # stick ".." at the top of the list
            sort_key = -1 if not reverse_sort else 32503680000  # Y3K problem
        return Sortable(
            sort_key,
            time.strftime("%b %d %H:%M", time.localtime(e.mtime)),
            style=style,
        )

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
        subtitle = (
            f"{total_size_str} in {ls.file_count} files | {ls.dir_count} dirs"
        )
        if self.glob is not None:
            subtitle = f"[red]{self.glob}[/red] | {subtitle}"
        self.border_subtitle = subtitle

    def reset_selection(self):
        self.selection = set()

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
        # TODO: when following links, keep track of actual "previous" dir
        self.post_message(
            self.Selected(
                path=(self.path / event.row_key.value).resolve(),  # type: ignore
                file_list=self,
            )
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        self.cursor_path = self.path / event.row_key.value  # type: ignore

    def on_descendant_focus(self):
        self.active = True
        self.add_class("focused")

    def on_descendant_blur(self):
        self.active = False
        self.remove_class("focused")

    def on_key(self, event: events.Key) -> None:
        # FIXME: shouldn't DataTable default bindings do the same?
        # TODO: also allow ctrl+d and ctrl+b to scroll by page?
        if event.key == "j":
            new_coord = (self.table.cursor_coordinate[0] + 1, 0)
            self.table.cursor_coordinate = new_coord  # type: ignore
        elif event.key == "k":
            new_coord = (self.table.cursor_coordinate[0] - 1, 0)
            self.table.cursor_coordinate = new_coord  # type: ignore
        elif event.key == "g":
            self.table.cursor_coordinate = (0, 0)  # type: ignore
        elif event.key == "G":
            self.table.cursor_coordinate = (self.table.row_count - 1, 0)  # type: ignore
        # FIXME: refactor to use actions?
        elif event.key == "b":
            self.post_message(self.Selected(path=self.path.parent, file_list=self))
        elif event.key == "backspace":
            self.post_message(self.Selected(path=self.path.parent, file_list=self))
        elif event.key == "r":
            self.update_listing()
        elif event.key == "space":
            key = self.cursor_path.name
            if key in self.selection:
                self.selection.remove(key)
            else:
                self.selection.add(key)
            self.update_listing()
            new_coord = (self.table.cursor_coordinate[0] + 1, 0)
            self.table.cursor_coordinate = new_coord  # type: ignore
