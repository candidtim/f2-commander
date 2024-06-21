import subprocess
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Footer

from .widgets.copy import CopyScreen
from .widgets.move import MoveScreen
from .widgets.delete import DeleteScreen
from .widgets.filelist import FileList

from .shell import editor, viewer


class TextualCommander(App):
    CSS_PATH = "tcss/main.tcss"
    BINDINGS = [
        Binding("v", "view", "View"),
        Binding("e", "edit", "Edit"),
        Binding("c", "copy", "Copy"),
        Binding("m", "move", "Move"),
        Binding("d", "delete", "Delete"),
        Binding("q", "quit", "Quit"),
        Binding("h", "toggle_hidden", "Toggle hidden files", show=False),
    ]

    left_path = reactive(Path.cwd())
    right_path = reactive(Path.home())
    show_hidden = reactive(False)

    def compose(self) -> ComposeResult:
        self.left = FileList(id="left")
        self.right = FileList(id="right")
        with Horizontal():
            yield self.left
            yield self.right
        yield Footer()

    def watch_left_path(self, old_path: Path, new_path: Path):
        self.left.path = new_path

    def watch_right_path(self, old_path: Path, new_path: Path):
        self.right.path = new_path

    @on(FileList.Selected, "#left")
    def on_left_selected(self, event: FileList.Selected):
        if event.path.is_dir():
            self.left_path = event.path

    @on(FileList.Selected, "#right")
    def on_right_selected(self, event: FileList.Selected):
        if event.path.is_dir():
            self.right_path = event.path

    def action_toggle_hidden(self):
        self.show_hidden = not self.show_hidden

    def watch_show_hidden(self, old: bool, new: bool):
        self.left.show_hidden = new
        self.right.show_hidden = new

    @property
    def active_filelist(self) -> FileList:
        assert self.left.active or self.right.active
        return self.left if self.left.active else self.right

    @property
    def inactive_filelist(self) -> FileList:
        assert self.left.active or self.right.active
        return self.right if self.left.active else self.left

    def action_view(self):
        src = self.active_filelist.cursor_path
        if src.is_file():
            with self.app.suspend():
                editor_cmd = viewer(or_editor=True)
                completed_process = subprocess.run(editor_cmd + [str(src)])
                completed_process.check_returncode()  # TODO: handle gracefully

    def action_edit(self):
        src = self.active_filelist.cursor_path
        if src.is_file():
            with self.app.suspend():
                editor_cmd = editor()
                completed_process = subprocess.run(editor_cmd + [str(src)])
                completed_process.check_returncode()  # TODO: handle gracefully

    def action_copy(self):
        def on_copy(result: bool):
            if result:
                self.inactive_filelist.update_listing()

        src = self.active_filelist.cursor_path
        dst = self.inactive_filelist.path
        self.push_screen(CopyScreen(src, dst), on_copy)

    def action_move(self):
        def on_move(result: bool):
            if result:
                self.active_filelist.update_listing()
                self.inactive_filelist.update_listing()

        src = self.active_filelist.cursor_path
        dst = self.inactive_filelist.path
        self.push_screen(MoveScreen(src, dst), on_move)

    def action_delete(self):
        def on_delete(result: bool):
            if result:
                self.active_filelist.update_listing()

        path = self.active_filelist.cursor_path
        self.push_screen(DeleteScreen(path), on_delete)
