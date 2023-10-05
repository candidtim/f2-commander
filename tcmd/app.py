from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Footer

from .widgets.copy import CopyScreen
from .widgets.filelist import FileList
from .widgets.view import ViewScreen


class TextualCommander(App):
    CSS_PATH = "tcss/main.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("v", "view", "View"),
        Binding("c", "copy", "Copy"),
        Binding("h", "toggle_hidden", "Toggle hidden files", show=False),
        Binding("f", "show_focus", "Show focus", show=False),  # FIXME: remove
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
            self.push_screen(ViewScreen(src))

    def action_copy(self):
        def on_copy(result: bool):
            if result:
                self.inactive_filelist.update_listing()

        src = self.active_filelist.cursor_path
        dst = self.inactive_filelist.path
        self.push_screen(CopyScreen(src, dst), on_copy)

    def action_show_focus(self):
        raise Exception(self.focused)
