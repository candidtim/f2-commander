import os
import shutil
import subprocess
from importlib.metadata import version
from pathlib import Path

from send2trash import send2trash
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Footer

from .shell import editor, shell, viewer
from .widgets.dialogs import InputDialog, StaticDialog, Style
from .widgets.filelist import FileList


class TextualCommander(App):
    CSS_PATH = "tcss/main.tcss"
    BINDINGS = [
        Binding("v", "view", "View"),
        Binding("e", "edit", "Edit"),
        Binding("c", "copy", "Copy"),
        Binding("m", "move", "Move"),
        Binding("d", "delete", "Delete"),
        # TODO: mkdir
        Binding("ctrl+n", "mkdir", "New dir"),
        # TODO: allow selecting multiple files (spacebar) before op
        Binding("x", "shell", "Shell"),
        # TODO: navigate the list (quick search by typing)
        # TODO: navigate to path (enter path)
        # TODO: set and navigate to bookmarks
        Binding("q", "quit_confirm", "Quit"),
        Binding("h", "toggle_hidden", "Toggle hidden files", show=False),
        Binding("?", "about", "About", show=False),
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
        footer = Footer()
        footer.compact = True
        footer.ctrl_to_caret = False
        footer.upper_case_keys = True
        yield footer

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
            viewer_cmd = viewer(or_editor=True)
            if viewer_cmd is not None:
                with self.app.suspend():
                    completed_process = subprocess.run(viewer_cmd + [str(src)])
                exit_code = completed_process.returncode
                if exit_code != 0:
                    msg = f"Viewer exited with an error ({exit_code})"
                    self.push_screen(StaticDialog.warning("Warning", msg))
            else:
                self.push_screen(StaticDialog.error("Error", "No viewer found!"))

    def action_edit(self):
        src = self.active_filelist.cursor_path
        if src.is_file():
            editor_cmd = editor()
            if editor_cmd is not None:
                with self.app.suspend():
                    completed_process = subprocess.run(editor_cmd + [str(src)])
                exit_code = completed_process.returncode
                if exit_code != 0:
                    msg = f"Editor exited with an error ({exit_code})"
                    self.push_screen(StaticDialog.warning("Error", msg))
            else:
                self.push_screen(StaticDialog.error("Error", "No editor found!"))

    def action_copy(self):
        src = self.active_filelist.cursor_path
        dst = self.inactive_filelist.path

        def on_copy(result: str | None):
            if result is not None:
                if src.is_dir():
                    shutil.copytree(src, os.path.join(result, src.name))
                else:
                    shutil.copy2(src, result)
                self.inactive_filelist.update_listing()

        self.push_screen(
            InputDialog(title=f"Copy {src.name} to", value=str(dst), btn_ok="Copy"),
            on_copy,
        )

    def action_move(self):
        src = self.active_filelist.cursor_path
        dst = self.inactive_filelist.path

        def on_move(result: str | None):
            if result is not None:
                shutil.move(src, result)
                self.active_filelist.update_listing()
                self.inactive_filelist.update_listing()

        self.push_screen(
            InputDialog(title=f"Move {src.name} to", value=str(dst), btn_ok="Move"),
            on_move,
        )

    def action_delete(self):
        path = self.active_filelist.cursor_path

        # TODO: allow delete, instead of moving to Trash
        def on_delete(result: bool):
            if result:
                send2trash(path)
                self.active_filelist.update_listing()

        self.push_screen(
            StaticDialog(
                title="Delete?",
                message=f"This will move {path.name} to Trash",
                btn_ok="Delete",
                style=Style.DANGER,
            ),
            on_delete,
        )

    def action_mkdir(self):
        pass

    def action_shell(self):
        shell_cmd = shell()
        if shell_cmd is not None:
            with self.app.suspend():
                completed_process = subprocess.run(
                    shell_cmd,
                    cwd=self.active_filelist.path,
                )
            self.active_filelist.update_listing()
            self.inactive_filelist.update_listing()
            exit_code = completed_process.returncode
            if exit_code != 0:
                msg = f"Editor exited with an error ({exit_code})"
                self.push_screen(StaticDialog.warning("Error", msg))
        else:
            self.push_screen(StaticDialog.error("Error", "No shell found!"))

    def action_quit_confirm(self):
        def on_confirm(result: bool):
            if result:
                self.exit()

        self.push_screen(StaticDialog("Quit?"), on_confirm)

    def action_about(self):
        msg = f"Textual Commander {version('textual-commander')}"
        self.push_screen(StaticDialog.info("About", msg))
