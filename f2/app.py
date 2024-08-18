# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import os
import shutil
import subprocess
from functools import partial
from importlib.metadata import version

from send2trash import send2trash
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Provider
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Footer

from .commands import Command
from .config import config, set_user_has_accepted_license, user_has_accepted_license
from .shell import editor, shell, viewer
from .widgets.dialogs import InputDialog, StaticDialog, Style
from .widgets.filelist import FileList
from .widgets.panel import Panel


class F2AppCommands(Provider):
    @property
    def all_commands(self):
        app_commands = [(self.app, cmd) for cmd in self.app.BINDINGS_AND_COMMANDS]
        flist = self.app.active_filelist
        flist_commands = [(flist, cmd) for cmd in flist.BINDINGS_AND_COMMANDS]
        return app_commands + flist_commands

    def _fmt_help(self, cmd):
        if cmd.binding_key is not None:
            return f"[{cmd.binding_key}]\n{cmd.description}\n"
        else:
            return f"{cmd.description}\n"

    async def search(self, query: str):
        matcher = self.matcher(query)
        for node, cmd in self.all_commands:
            score = matcher.match(cmd.name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(cmd.name),
                    partial(node.run_action, cmd.action),
                    help=self._fmt_help(cmd),
                )

    async def discover(self):
        for node, cmd in self.all_commands:
            yield DiscoveryHit(
                cmd.name,
                partial(node.run_action, cmd.action),
                help=self._fmt_help(cmd),
            )


class F2Commander(App):
    CSS_PATH = "tcss/main.tcss"
    BINDINGS_AND_COMMANDS = [
        Command(
            "swap_panels",
            "Swap panels",
            "Swap left and right panels",
            "ctrl+w",
        ),
        Command(
            "same_location",
            "Same location in other panel",
            "Open the same location in the other (inactive) panel",
            "ctrl+s",
        ),
        Command(
            "change_left_panel",
            "Left panel",
            "Change the left panel type",
            "ctrl+e",
        ),
        Command(
            "change_right_panel",
            "Right panel",
            "Change the right panel type",
            "ctrl+r",
        ),
        Command(
            "toggle_hidden",
            "Togghle hidden",
            "Show or hide hidden files",
            "h",
        ),
        Command(
            "toggle_dirs_first",
            "Toggle dirs first",
            "Show directories first or ordered among files",
            None,
        ),
        Command(
            "toggle_order_case_sensitive",
            "Toggle case sensitive name order",
            "Whether name ordering is case sensitive or not",
            None,
        ),
        Command(
            "toggle_dark",
            "Toggle theme",
            "Switch between dark and light themes",
            None,
        ),
        Command(
            "about",
            "About",
            "Information about this software",
            None,
        ),
    ]
    BINDINGS = [
        Binding("?", "help", "Help"),
        Binding("v", "view", "View"),
        Binding("e", "edit", "Edit"),
        Binding("c", "copy", "Copy"),
        Binding("m", "move", "Move"),
        Binding("d", "delete", "Delete"),
        Binding("ctrl+n", "mkdir", "New dir"),
        Binding("x", "shell", "Shell"),
        # FIXME: following exists only for discoverability, remove when textual does it
        Binding("ctrl+\\", "do_nothing", "Command Palette"),
        Binding("q", "quit_confirm", "Quit"),
    ] + [
        Binding(cmd.binding_key, cmd.action, cmd.description, show=False)
        for cmd in BINDINGS_AND_COMMANDS
        if cmd.binding_key is not None
    ]  # type: ignore
    COMMANDS = {F2AppCommands}

    show_hidden = reactive(config.show_hidden)
    dirs_first = reactive(config.dirs_first)
    order_case_sensitive = reactive(config.order_case_sensitive)
    swapped = reactive(False)

    def compose(self) -> ComposeResult:
        self.panels_container = Horizontal()
        self.panel_left = Panel("left", id="left")
        self.panel_right = Panel("right", id="right")
        with self.panels_container:
            yield self.panel_left
            yield self.panel_right
        footer = Footer()
        footer.compact = True
        footer.ctrl_to_caret = False
        footer.upper_case_keys = True
        yield footer

    def action_toggle_hidden(self):
        self.show_hidden = not self.show_hidden

    def watch_show_hidden(self, old: bool, new: bool):
        self.left.show_hidden = new
        self.right.show_hidden = new
        config.show_hidden = new

    def action_toggle_dirs_first(self):
        self.dirs_first = not self.dirs_first

    # TODO: save default value to user options, restore on start
    def watch_dirs_first(self, old: bool, new: bool):
        self.left.dirs_first = new
        self.right.dirs_first = new
        config.dirs_first = new

    def action_toggle_order_case_sensitive(self):
        self.order_case_sensitive = not self.order_case_sensitive

    # TODO: save default value to user options, restore on start
    def watch_order_case_sensitive(self, old: bool, new: bool):
        self.left.order_case_sensitive = new
        self.right.order_case_sensitive = new
        config.order_case_sensitive = new

    def action_swap_panels(self):
        self.swapped = not self.swapped

    def watch_swapped(self, old: bool, new: bool):
        if new:
            self.panels_container.move_child(self.panel_left, after=self.panel_right)
        else:
            self.panels_container.move_child(self.panel_left, before=self.panel_right)

    def action_same_location(self):
        self.inactive_filelist.path = self.active_filelist.path

    def action_change_left_panel(self):
        # TODO: after swap this "right"
        # FIXME: there is no left/right at all? Panel A and panel B instead?
        self.panel_left.action_change_panel()

    def action_change_right_panel(self):
        self.panel_right.action_change_panel()

    @property
    def left(self):
        return self.query_one("#left > *")

    @property
    def right(self):
        return self.query_one("#right > *")

    # FIXME: left/right are not necessarily FileList; make Optional and handle None
    @property
    def active_filelist(self) -> FileList:
        return self.left if self.left.active else self.right

    @property
    def inactive_filelist(self) -> FileList:
        return self.right if self.left.active else self.left

    @work
    async def on_mount(self, event):
        if not user_has_accepted_license():
            self.action_about()

    @on(FileList.Selected)
    def on_file_selected(self, event: FileList.Selected):
        for c in self.query("Panel > *"):
            if hasattr(c, "on_other_panel_selected"):
                c.on_other_panel_selected(event.path)

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
        sources = self.active_filelist.selected_paths()
        dst = self.inactive_filelist.path

        def on_copy(result: str | None):
            if result is not None:
                for src in sources:
                    if src.is_dir():
                        shutil.copytree(src, os.path.join(result, src.name))
                    else:
                        shutil.copy2(src, result)
                # FIXME: broken abstraction, at least have a function to reset it?
                self.active_filelist.selection = set()
                self.active_filelist.update_listing()
                self.inactive_filelist.update_listing()

        msg = (
            f"Copy {sources[0].name} to"
            if len(sources) == 1
            else f"Copy {len(sources)} selected entries to"
        )
        self.push_screen(
            InputDialog(title=msg, value=str(dst), btn_ok="Copy"),
            on_copy,
        )

    def action_move(self):
        sources = self.active_filelist.selected_paths()
        dst = self.inactive_filelist.path

        def on_move(result: str | None):
            if result is not None:
                for src in sources:
                    shutil.move(src, result)
                self.active_filelist.selection = set()
                self.active_filelist.update_listing()
                self.inactive_filelist.update_listing()

        msg = (
            f"Move {sources[0].name} to"
            if len(sources) == 1
            else f"Move {len(sources)} selected entries to"
        )
        self.push_screen(
            InputDialog(title=msg, value=str(dst), btn_ok="Move"),
            on_move,
        )

    def action_delete(self):
        paths = self.active_filelist.selected_paths()

        def on_delete(result: bool):
            if result:
                for path in paths:
                    send2trash(path)
                self.active_filelist.selection = set()
                self.active_filelist.update_listing()

        msg = (
            f"This will move {paths[0].name} to Trash"
            if len(paths) == 1
            else f"This will move {len(paths)} selected entries to Trash"
        )
        self.push_screen(
            StaticDialog(
                title="Delete?",
                message=msg,
                btn_ok="Delete",
                style=Style.DANGER,
            ),
            on_delete,
        )

    def action_mkdir(self):
        def on_mkdir(result: str | None):
            if result is not None:
                new_dir_path = self.active_filelist.path / result
                new_dir_path.mkdir(parents=True, exist_ok=True)
                self.active_filelist.update_listing()

        self.push_screen(
            InputDialog("New directory", btn_ok="Create"),
            on_mkdir,
        )

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
                msg = f"Shell exited with an error ({exit_code})"
                self.push_screen(StaticDialog.warning("Warning", msg))
        else:
            self.push_screen(StaticDialog.error("Error", "No shell found!"))

    def action_quit_confirm(self):
        def on_confirm(result: bool):
            if result:
                self.exit()

        self.push_screen(StaticDialog("Quit?"), on_confirm)

    def action_about(self):
        def on_dismiss(result):
            set_user_has_accepted_license()

        title = f"F2 Commander {version('f2-commander')}"
        msg = (
            'This application is provided "as is", without warranty of any kind.\n'
            "This application is licensed under the Mozilla Public License, v. 2.0.\n"
            "You can find a copy of the license at https://mozilla.org/MPL/2.0/"
        )
        self.push_screen(StaticDialog.info(title, msg, classes="large"), on_dismiss)

    def action_help(self):
        self.panel_right.panel_type = "help"

    def action_do_nothing(self):
        pass
