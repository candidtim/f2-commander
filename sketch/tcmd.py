import os
import stat
import time

from humanize import naturalsize
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Static


class FilePane(Static):
    def __init__(self, path, *args, **kwargs):
        self.path = path
        super().__init__(*args, **kwargs)

    def stat_to_row(self, path, s):
        return

    def compose(self) -> ComposeResult:
        self.table = DataTable()
        yield self.table

    def on_mount(self) -> None:
        self.table.cursor_type = "row"
        self.table.add_columns("Name", "│", "Size", "│", "Modify Time")
        self._update()

    def _update(self) -> None:
        self.table.clear()
        self.table.add_row(
            "..",
            Text("│", style="cyan1"),
            "<Up>",
            Text("│", style="cyan1"),
            "",
            key="..",
        )
        file_count = 0
        dir_count = 0
        for name in os.listdir(self.path):
            path = os.path.join(self.path, name)
            os_stat = os.lstat(path)
            is_dir = stat.S_ISDIR(os_stat.st_mode)
            is_hidden = name.startswith(".")
            style = "cyan1"
            if is_dir:
                style = "bright_white"
            elif is_hidden:
                style = "grey70"
            self.table.add_row(
                Text(name, style=style),
                Text("│", style="cyan1"),
                Text(
                    "<Dir>" if is_dir else naturalsize(os_stat.st_size, gnu=True),
                    style=style,
                ),
                Text("│", style="cyan1"),
                Text(
                    time.strftime("%b %d  %H:%M", time.localtime(os_stat.st_mtime)),
                    style=style,
                ),
                key=name,
            )
            if is_dir:
                dir_count += 1
            else:
                file_count += 1
        self.border_title = self.path
        self.border_subtitle = f"files: {file_count}, dirs: {dir_count}"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        selected_path = os.path.join(self.path, event.row_key.value)
        if os.path.isdir(selected_path):
            self.path = os.path.normpath(selected_path)
            self._update()
        # TODO: if new path is a parent dir, scroll to the source dir


class CommandLine(Static):
    pass


class AppFooter(Static):
    def compose(self) -> ComposeResult:
        self.cmd_line = CommandLine("> ")
        yield self.cmd_line
        yield Footer()


class TextualCommander(App):
    CSS_PATH = "tcmd.tcss"
    BINDINGS = [
        ("h", "help", "Help"),
        ("m", "menu", "Menu"),  # UserMn
        ("v", "view", "View"),
        ("e", "edit", "Edit"),
        ("c", "copy", "Copy"),
        ("r", "rename", "RenMov"),  # RenMov
        ("k", "makedir", "MkDir"),
        ("d", "delete", "Delete"),
        ("u", "pulldn", "Pull Down"),  # ConfMn
        ("p", "plugin", "Plugin"),
        ("s", "screen", "Screen"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, left_dir, right_dir, *args, **kwargs):
        self.left_dir = left_dir
        self.right_dir = right_dir
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        self.left_pane = FilePane(self.left_dir)
        self.right_pane = FilePane(self.right_dir)
        self.footer = AppFooter()

        with Horizontal():
            yield self.left_pane
            yield self.right_pane
        yield self.footer

    def on_mount(self) -> None:
        self.left_pane.border_title = self.left_dir
        self.left_pane.border_subtitle = "files: 10, folders: 2"
        self.right_pane.border_title = self.right_dir
        self.right_pane.border_subtitle = "files: 2, folders: 15"


if __name__ == "__main__":
    app = TextualCommander(os.getcwd(), os.path.expanduser("~"))
    app.run()
