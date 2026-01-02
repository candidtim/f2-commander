# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import dataclasses
import functools
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from humanize import naturalsize
from rich.text import Text
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.fuzzy import FuzzySearch
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DataTable, Input, Static
from textual.widgets.data_table import RowDoesNotExist

from f2.commands import Command
from f2.fs.node import Node
from f2.fs.util import shorten
from f2.shell import native_open


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
            "search",
            "Incremental search",
            "Incremental search in the file list, with fuzzy matching",
            "/",
        ),
        Command(
            "open_in_os_file_manager",
            "Open in OS file manager",
            "Open current location in the default OS file manager",
            "o",
        ),
        Command(
            "calc_dir_size",
            "Calculate directory size",
            "Calculate the size of the directory tree",
            "ctrl+@",  # this is `ctrl+space`
        ),
    ]
    BINDINGS = [  # type: ignore
        Binding(cmd.binding_key, cmd.action, cmd.description, show=False)
        for cmd in BINDINGS_AND_COMMANDS
        if cmd.binding_key is not None
    ]

    COLUMN_PADDING = 2  # a column uses this many chars more to render
    SCROLLBAR_SIZE = 2
    TIME_FORMAT = "%b %d %H:%M"

    class Navigated(Message):
        def __init__(self, node: Node, control: "FileList"):
            self.node = node
            self._control = control
            super().__init__()

        @property
        def contol(self) -> "FileList":
            return self._control

    class Selected(Message):
        def __init__(self, node: Node, control: "FileList"):
            self.node = node
            self._control = control
            super().__init__()

        @property
        def contol(self) -> "FileList":
            return self._control

    class Open(Message):
        def __init__(self, node: Node, control: "FileList"):
            self.node = node
            self._control = control
            super().__init__()

        @property
        def contol(self) -> "FileList":
            return self._control

    # FIMXE: do all these need to be reactive?

    # primary model:
    node: reactive[Node] = reactive(Node.cwd(), init=False)
    cursor_node: reactive[Node] = reactive(Node.cwd())

    # state:
    active = reactive(False)

    # toggles:
    sort_options = reactive(SortOptions("name"), init=False)
    show_hidden = reactive(False, init=False)
    dirs_first = reactive(False, init=False)
    order_case_sensitive = reactive(False, init=False)
    search_mode = reactive(None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.listing: list[Node] = []
        self._selection: set[Node] = set()

    def compose(self) -> ComposeResult:
        self.table: DataTable = DataTable(cursor_type="row")
        self.search_input: Input = Input(
            classes="search hidden",
            placeholder="Quick search (Esc or Enter to exit)",
        )
        with Vertical():
            yield self.table
            yield self.search_input

    def on_mount(self) -> None:
        self._add_columns()
        self.node = self.app.get_cwd(self)

    def _add_columns(self):
        self.table.add_column("Name", key="name")
        self.table.add_column("Size", key="size")
        self.table.add_column("Modified", key="mtime")

    @work
    async def on_resize(self, event):
        self.table.clear(columns=True)
        self._add_columns()
        self.update_listing()
        self.watch_sort_options(None, self.sort_options)
        # FIXME: calling internal API here (_update_dimensions) to avoid
        #        narrow columns when the parent window is resized:
        self.table._update_dimensions(self.table.rows)

    @property
    def selection(self) -> list[Node]:
        if len(self._selection) > 0:
            nodes = list([TextAndValue(node, node.name) for node in self._selection])
            ordered = sorted(nodes, key=self.sort_key)
            if self.sort_options.reverse:
                ordered = reversed(ordered)  # type: ignore
            return [c.value for c in ordered]
        elif self.cursor_node != self.node.parent:
            return [self.cursor_node]
        else:
            return []

    def reset_selection(self):
        self._selection = set()

    def add_selection(self, node: Node):
        if node == self.node.parent:
            return
        self._selection.add(node)

    def remove_selection(self, node: Node):
        self._selection.remove(node)

    def toggle_selection(self, node: Node):
        if node in self._selection:
            self.remove_selection(node)
        else:
            self.add_selection(node)

    def scroll_to_entry(self, name: str):
        try:
            idx = self.table.get_row_index(name)
            self.table.cursor_coordinate = (idx, 0)  # type: ignore
        except RowDoesNotExist:
            pass

    #
    # FORMATTING:
    #

    def _row_style(self, node: Node) -> str:
        style = set()

        if node.is_link:
            style.add("underline")
        elif node.is_dir:
            style.add("bold")
        elif node.is_executable:
            style.add(self.app.theme_.error or "red")  # type: ignore
        elif node.is_hidden:
            style.add("dim")
        elif node.is_archive:
            style.add(self.app.theme_.accent or "yellow")  # type: ignore

        if node in self._selection:
            # adds a background color:
            style.add(self.app.theme_.accent or "yellow")  # type: ignore
            style.add("italic")

        return " ".join(sorted(style))

    def _fmt_name(self, node: Node, style: str) -> Text:
        text = Text()

        width_target = self._width_name()
        if not width_target:
            # container width is not known yet => assume smallest size, let the
            # container render once, then render the text on the next round
            return text

        # adjust width: cut long names
        if len(node.name) > width_target:
            suffix = "..."
            cut_idx = width_target - len(suffix)
            text.append(node.name[:cut_idx] + suffix, style=style)

        # FIXME: remove if textual supports full-width data tables
        # adjust width: pad short names to span the column
        else:
            pad_size = width_target - len(node.name)
            text.append(node.name, style=style)
            text.append(" " * pad_size)

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

    def _fmt_size(self, node: Node, style: str) -> Text:
        if node.name == "..":
            return Text("-- UP⇧ --", style=style, justify="center")
        elif node.is_dir:
            return Text("-- DIR --", style=style, justify="center")
        elif node.is_link:
            return Text("-- LNK --", style=style, justify="center")
        else:
            return Text(naturalsize(node.size), style=style, justify="right")

    @functools.cache
    def _width_size(self):
        return len(naturalsize(123)) + self.COLUMN_PADDING

    def _fmt_mtime(self, node: Node, style: str) -> Text:
        return Text(
            time.strftime(self.TIME_FORMAT, time.localtime(node.mtime)),
            style=style,
        )

    @functools.cache
    def _width_mtime(self):
        return len(time.strftime(self.TIME_FORMAT)) + self.COLUMN_PADDING

    #
    # END OF FORMATTING
    #

    #
    # ORDERING:
    #

    def sort_key(self, name_and_value):
        sort_key_fn = {
            "name": self.sort_key_by_name,
            "size": self.sort_key_by_size,
            "mtime": self.sort_key_by_mtime,
        }[self.sort_options.key]
        entry: Node = name_and_value.value
        return sort_key_fn(entry)

    def sort_key_by_name(self, node: Node) -> str:
        # stick ".." at the top of the list, regardless of the order (asc/desc)
        if node.name == "..":
            return "\u0000" if not self.sort_options.reverse else "\uffff"

        # dirs first, if asked for
        prefix = ""
        if self.dirs_first and node.is_dir:
            prefix = "\u0001" if not self.sort_options.reverse else "\ufffe"

        # handle case sensetivity
        name = node.name
        if not self.order_case_sensitive:
            name = name.lower() + name  # keeping original name for stable ordering

        return prefix + name

    def sort_key_by_size(self, node: Node) -> Tuple[int, Optional[str]]:
        max_file_size = 2**64  # maximum file size in zfs, and probably on the planet
        # stick ".." at the top of the list, regardless of the order (asc/desc)
        if node.name == "..":
            size_key = -1 if not self.sort_options.reverse else max_file_size + 1
            return (size_key, None)

        size_key = node.size
        # when ordering by size, dirs are always first to avoid confusion
        if node.is_dir or node.is_link:
            size_key = 0 if not self.sort_options.reverse else max_file_size

        return (size_key, self.sort_key_by_name(node))  # add name for stable ordering

    def sort_key_by_mtime(self, node: Node) -> Tuple[float, Optional[str]]:
        y3k = 32_503_680_000  # this program has Y3K issues
        # stick ".." at the top of the list, regardless of the order (asc/desc)
        if node.name == "..":
            key = -1 if not self.sort_options.reverse else 2 * y3k
            return (key, None)

        mtime_key = node.mtime
        if self.dirs_first:
            if not self.sort_options.reverse and not node.is_dir:
                mtime_key = node.mtime + y3k
            elif self.sort_options.reverse and node.is_dir:
                mtime_key = node.mtime + y3k

        return (mtime_key, self.sort_key_by_name(node))  # add name for stable ordering

    #
    # END OF ORDERING
    #

    def _update_table(self):
        self.table.clear()
        for node in self.listing:
            if not self.show_hidden and node.is_hidden:
                continue

            style = self._row_style(node)
            self.table.add_row(
                # name column also holds original values: (FIXME...)
                TextAndValue(node, self._fmt_name(node, style)),
                self._fmt_size(node, style),
                self._fmt_mtime(node, style),
                key=node.name,
            )
        # FIXME: why reset the sort to name? presrve the previous sort method!
        self.table.sort("name", key=self.sort_key, reverse=self.sort_options.reverse)

    def update_listing(self):
        prev_cursor_node = self.cursor_node

        ls = self.node.list()
        if self.node.parent:
            up = dataclasses.replace(self.node.parent, name="..")
            ls.insert(0, up)
        self.listing = ls

        self._update_table()

        # if stil in same dir as before, restore the cursor position
        if self.node == prev_cursor_node.parent:
            self.scroll_to_entry(prev_cursor_node.name)

        # top border: "current" path
        if self.node.is_local:
            self.parent.border_title = shorten(
                self.node.path,
                width_target=self.table.size.width - 4,
                method="slice",
                unexpand_home=self.node.is_local,
            )
        elif self.node.is_archive:
            self.parent.border_title = self.node.path
        else:
            self.parent.border_title = self.node.fs.unstrip_protocol(self.node.path)

        # bottom border: add information about the directory:
        total_size = naturalsize(sum(node.size for node in ls if node.name != ".."))
        file_count = sum(1 for node in ls if node.is_file and not node.is_link)
        dir_count = sum(
            1 for node in ls if node.is_dir and not node.is_link and node.name != ".."
        )
        subtitle = f"{total_size} in {file_count} files | {dir_count} dirs"
        self.parent.border_subtitle = subtitle

    def watch_node(self, old_node: Node, new_node: Node):
        # if trying to navigate to a file, navigate to its parent dir:
        if not new_node.is_dir:
            self.set_reactive(FileList.node, new_node.parent)  # type: ignore

        self.reset_selection()
        self.update_listing()

        # if navigated "up", select source dir in the new list:
        if new_node == old_node.parent:
            self.scroll_to_entry(old_node.name)

        # if nvaigated to a file, select it:
        if not new_node.is_dir:
            self.scroll_to_entry(new_node.basename)

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
        if old is not None:
            prev_sort_col = self.table.columns[old.key]  # type: ignore
            prev_sort_col.label = prev_sort_col.label[:-2]
        # add the new sort label:
        new_sort_col = self.table.columns[new.key]  # type: ignore
        direction = "⬆" if new.reverse else "⬇"
        new_sort_col.label = f"{new_sort_col.label} {direction}"  # type: ignore

    # FIXME: refactor (simplify) ordering logic; see if DataTable provides better API
    def action_order(self, key: str, reverse: bool):
        # if the user chooses the same order again, reverse it:
        # (e.g., pressing `n` twice will reverse the order the second time)
        new_sort_options = SortOptions(key, reverse)
        if self.sort_options == new_sort_options:
            new_sort_options = SortOptions(key, not reverse)
        self.sort_options = new_sort_options

    def on_data_table_header_selected(self, event):
        key = event.column_key.value
        self.action_order(key, False)

    def action_search(self):
        self.search_mode = True
        self.refresh_bindings()
        self.search_input.remove_class("hidden")
        self.search_input.focus()

    def dismiss_search(self):
        with self.search_input.prevent(Input.Changed):
            self.search_input.value = ""
        self.table.focus()
        self.search_input.add_class("hidden")
        self.search_mode = False
        self.refresh_bindings()

    @on(Input.Submitted, ".search")
    def on_search_input_submitted(self, event: Input.Submitted):
        self.dismiss_search()

    @on(Input.Changed, ".search")
    def on_search_input_changed(self, event: Input.Changed):
        if not event.value:
            return

        matcher = FuzzySearch()
        query = event.value
        names: list[str] = [key.value for key in self.table.rows]  # type: ignore
        scores = [matcher.match(query, name)[0] for name in names]
        max_score = max(scores)
        if max_score > 0:
            idx = scores.index(max_score)
            name = names[idx]
            self.scroll_to_entry(name)

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        node_name: str = event.row_key.value  # type: ignore
        nodes = [n for n in self.listing if n.name == node_name]
        if len(nodes) == 1 and nodes[0]:
            node = nodes[0]
            if node.is_dir or node.is_archive:
                self.node = node
                self.post_message(self.Navigated(self.node, self))

    def action_open(self):
        # "open" is handled separately from "table.row_selected" to distinguish
        # between "enter" and mouse click (avoid navigation and running
        # apps on mouse click)
        if self.cursor_node.is_file:
            self.post_message(self.Open(self.cursor_node, self))

    def action_open_in_os_file_manager(self):
        if not self.node.is_local:
            return

        # FIXME: the rest of code does not belong to the action implementation?
        open_cmd = native_open()
        if open_cmd is not None:
            self.app.subprocess_run(open_cmd, self.node.path)
            self.app.refresh()

    @work(thread=True)
    async def action_calc_dir_size(self):
        node = self.cursor_node  # hold on to the requsted node
        self.table.action_cursor_down()  # and move the cursor

        if not node.is_dir:
            return

        style = self._row_style(node)

        # show a placeholder first:
        placeholder = Text("...", style=style, justify="right")
        self.table.update_cell(node.name, "size", placeholder)

        # then, calculate and show the size (can be slow):
        size = self.node.fs.du(node.path, total=True, withdirs=True)
        size_text = Text(naturalsize(size), style=style, justify="right")
        self.table.update_cell(node.name, "size", size_text)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        name: str = event.row_key.value  # type: ignore
        self.cursor_node = next(n for n in self.listing if n.name == name)
        self.post_message(self.Selected(self.cursor_node, self))

    def focus(self):
        self.table.focus()

    def on_descendant_focus(self, event):
        self.active = True
        self.add_class("focused")

    def on_descendant_blur(self, event):
        self.active = False
        self.remove_class("focused")
        if event.widget == self.search_input:
            self.dismiss_search()

    def on_key(self, event: events.Key) -> None:
        if self.search_mode:
            self.on_key_search_mode(event)
        else:
            self.on_key_normal_mode(event)

    def on_key_search_mode(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss_search()

    def on_key_normal_mode(self, event: events.Key) -> None:
        if event.key == "tab":
            self.app.focus_next_panel()
            event.stop()
        elif event.key == "j":
            self.table.action_cursor_down()
        elif event.key == "k":
            self.table.action_cursor_up()
        elif event.key in ("g", "home"):
            self.table.action_scroll_top()
        elif event.key in ("G", "end"):
            self.table.action_scroll_bottom()
        elif event.key in ("ctrl+d"):
            scroll_height = (self.table.scrollable_content_region.height - 2) // 2
            for i in range(scroll_height):
                self.table.action_cursor_down()
        elif event.key in ("ctrl+u"):
            scroll_height = (self.table.scrollable_content_region.height - 2) // 2
            for i in range(scroll_height):
                self.table.action_cursor_up()
        elif event.key in ("ctrl+f"):
            self.table.action_page_down()
        elif event.key in ("ctrl+b"):
            self.table.action_page_up()
        elif event.key == "backspace":
            if self.node.parent:
                self.node = self.node.parent
        elif event.key == "R":
            self.update_listing()
        elif event.key == "enter":
            self.action_open()
        elif event.key in ("space", "J", "shift+down"):
            self.toggle_selection(self.cursor_node)
            self.update_listing()
            self.table.action_cursor_down()
        elif event.key in ("K", "shift+up"):
            self.toggle_selection(self.cursor_node)
            self.update_listing()
            self.table.action_cursor_up()
        elif event.key == "minus":
            self.reset_selection()
            self.update_listing()
        elif event.key == "plus":
            for node in self.listing:
                self.add_selection(node)
            self.update_listing()
        elif event.key == "asterisk":
            for node in self.listing:
                self.toggle_selection(node)
            self.update_listing()
