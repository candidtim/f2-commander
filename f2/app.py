# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import os
import posixpath
import shlex
import subprocess
import tempfile
import time
from functools import partial
from importlib.metadata import version
from pathlib import Path
from typing import Optional, Union

import fsspec
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Provider
from textual.containers import Horizontal
from textual.content import Content
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import Footer, Label

from .commands import Command
from .config import FileSystem, config_root
from .errors import error_handler_async, with_error_handler
from .fs.arch import is_archive, open_archive, write_archive
from .fs.node import Node
from .fs.util import copy, copy_final_path, delete, mkdir, mkfile, move, rename
from .shell import default_editor, default_shell, default_viewer, native_open
from .update import check_for_updates
from .widgets.bookmarks import GoToBookmarkDialog
from .widgets.config import ConfigDialog
from .widgets.connect import ConnectToRemoteDialog
from .widgets.dialogs import InputDialog, StaticDialog, StaticDialogR, Style
from .widgets.filelist import FileList
from .widgets.panel import Panel
from .widgets.types import WithF2App


class F2AppCommands(Provider, WithF2App):
    @property
    def all_commands(self):
        app_commands = [(self.app_, cmd) for cmd in self.app_.BINDINGS_AND_COMMANDS]
        flist = self.app_.active_filelist
        flist_commands = (
            [(flist, cmd) for cmd in flist.BINDINGS_AND_COMMANDS] if flist else []
        )
        return app_commands + flist_commands

    def _fmt_name(self, cmd, text: Optional[Content] = None):
        t = text or Text(cmd.name)
        if cmd.binding_key is not None:
            t.append(" ")
            t.append(f"[{cmd.binding_key}]")
        return t

    async def search(self, query: str):
        matcher = self.matcher(query)
        for node, cmd in self.all_commands:
            score = matcher.match(cmd.name)
            if score > 0:
                yield Hit(
                    score,
                    self._fmt_name(cmd, matcher.highlight(cmd.name)),
                    partial(node.run_action, cmd.action),
                    help=f"{cmd.description}\n",
                )

    async def discover(self):
        for node, cmd in self.all_commands:
            yield DiscoveryHit(
                self._fmt_name(cmd),
                partial(node.run_action, cmd.action),
                help=f"{cmd.description}\n",
            )


class F2CommanderMeta(type):
    def __new__(metacls, clsname, bases, attrs):
        bases += (F2Commander,)
        attrs["__module__"] = F2Commander.__module__
        attrs["__qualname__"] = F2Commander.__qualname__
        attrs["BINDINGS"] = attrs["_BINDINGS"] + [
            Binding(cmd.binding_key, cmd.action, cmd.description, show=False)
            for cmd in F2Commander.BINDINGS_AND_COMMANDS
            if cmd.binding_key is not None
        ]
        del attrs["_BINDINGS"]
        return type(clsname, bases, attrs)


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
            "go_to_path",
            "Enter path",
            "Enter a path to jump to it",
            "ctrl+g",
        ),
        Command(
            "toggle_hidden",
            "Togghle hidden",
            "Show or hide hidden files",
            "h",
        ),
        Command(
            "rename",
            "Rename",
            "Rename a file or a directory",
            "M",
        ),
        Command(
            "mkfile",
            "Create a file",
            "Create a new file (touch)",
        ),
        Command(
            "archive",
            "Archive / compress files",
            "Archive and optionally compress current selection",
        ),
        Command(
            "connect",
            "Connect to remote",
            "Connect to a remote file system",
            "ctrl+t",
        ),
        Command(
            "configure",
            "Configuration",
            "Review and modify the app settings",
            "ctrl+comma",
        ),
        Command(
            "navigate_to_config",
            "Show the configuration directory",
            "Open the user's configuration directory in the file list",
        ),
        Command(
            "check_for_updates",
            "Check for updates",
            "Check if a newer version is available in PyPI",
        ),
        Command(
            "about",
            "About",
            "Information about this software",
        ),
    ]
    COMMANDS = {F2AppCommands}

    show_hidden = reactive(False, init=False)
    dirs_first = reactive(False, init=False)
    order_case_sensitive = reactive(False, init=False)
    swapped = reactive(False, init=False)

    def __init__(
        self,
        config,
        work_dir_left: Path,
        work_dir_right: Path,
        debug: bool = False,
    ):
        super().__init__()
        self.config = config
        self.cwd_left = Node.from_url(str(work_dir_left))
        self.cwd_right = Node.from_url(str(work_dir_right))
        self.f2_app_debug = debug  # avoid confusion with Textual's debug property

    def compose(self) -> ComposeResult:
        self.panels_container = Horizontal()
        self.panel_left = Panel("left", id="left")
        self.panel_right = Panel("right", id="right")
        with self.panels_container:
            yield self.panel_left
            yield self.panel_right
        if self.f2_app_debug:
            self.debug_info = Label(id="debug-info")
            self.debug_info.border_title = "Debug info"
            yield self.debug_info
        yield Footer()

    def _info(self, *args):
        """
        Set a message to the "Debug info" area.
        Only visiable with the --debug flag enabled.
        """
        if self.f2_app_debug:
            msg = " ".join([str(arg) for arg in args])
            self.debug_info.update(msg)

    @property
    def theme_(self) -> Theme:
        """Active Theme instance (App.theme is a theme name only)"""
        return self.app.available_themes[self.app.theme]

    def action_toggle_hidden(self):
        self.show_hidden = not self.show_hidden

    def watch_show_hidden(self, old: bool, new: bool):
        if self.left:
            self.left.show_hidden = new  # type: ignore
        if self.right:
            self.right.show_hidden = new  # type: ignore
        with self.config.autosave() as config:
            config.display.show_hidden = new

    def action_toggle_dirs_first(self):
        self.dirs_first = not self.dirs_first

    def watch_dirs_first(self, old: bool, new: bool):
        if self.left:
            self.left.dirs_first = new  # type: ignore
        if self.right:
            self.right.dirs_first = new  # type: ignore
        with self.config.autosave() as config:
            config.display.dirs_first = new

    def action_toggle_order_case_sensitive(self):
        self.order_case_sensitive = not self.order_case_sensitive

    def watch_order_case_sensitive(self, old: bool, new: bool):
        if self.left:
            self.left.order_case_sensitive = new  # type: ignore
        if self.right:
            self.right.order_case_sensitive = new  # type: ignore
        with self.config.autosave() as config:
            config.display.order_case_sensitive = new

    def action_swap_panels(self):
        self.swapped = not self.swapped

    def watch_swapped(self, old: bool, new: bool):
        # TODO: After the swap the "left" panel will on the right and vice versa.
        #       Maybe there is no left/right at all? Panel A and panel B instead?
        #       Or handle the swap by changing root paths (won't swap other types
        #       of panels, though)?
        if new:
            self.panels_container.move_child(self.panel_left, after=self.panel_right)
        else:
            self.panels_container.move_child(self.panel_left, before=self.panel_right)

    def action_same_location(self):
        if not self.active_filelist or not self.inactive_filelist:
            return
        self.inactive_filelist.node = self.active_filelist.node

    @work
    async def action_change_left_panel(self):
        self.panel_left.action_change_panel()

    @work
    async def action_change_right_panel(self):
        self.panel_right.action_change_panel()

    @property
    def left(self) -> Optional[Widget]:
        try:
            return self.query_one("#left > *")
        except NoMatches:
            return None

    @property
    def right(self) -> Optional[Widget]:
        try:
            return self.query_one("#right > *")
        except NoMatches:
            return None

    @property
    def active_filelist(self) -> Optional[FileList]:
        for panel in (self.left, self.right):
            if isinstance(panel, FileList) and panel.active:
                return panel
        return None

    @property
    def inactive_filelist(self) -> Optional[FileList]:
        for panel in (self.left, self.right):
            if isinstance(panel, FileList) and not panel.active:
                return panel
        return None

    @work
    async def on_mount(self, event):
        self.reload_config()
        if not self.config.startup.license_accepted:
            self.action_about()
        if self.config.startup.check_for_updates:
            self.action_check_for_updates(auto=True)

    def get_cwd(self, for_list: Optional[FileList]) -> Node:
        if for_list is None:
            for_list = self.active_filelist

        if for_list == self.left:
            return self.cwd_left
        else:
            return self.cwd_right

    def reload_config(self):
        self.show_hidden = self.config.display.show_hidden
        self.dirs_first = self.config.display.dirs_first
        self.order_case_sensitive = self.config.display.order_case_sensitive
        self.theme = self.config.display.theme

    @on(FileList.Navigated)
    def on_dir_navigated(self, event: FileList.Navigated):
        if event.control == self.left:
            self.cwd_left = event.node
        else:
            self.cwd_right = event.node

    @on(FileList.Selected)
    def on_file_selected(self, event: FileList.Selected):
        for c in self.query("Panel > *"):
            if hasattr(c, "on_other_panel_selected"):
                c.on_other_panel_selected(event.node)  # type: ignore

    def subprocess_run(self, cmd: str, *args, **kwargs) -> Optional[int]:
        """Run a command in a subprocess and return its exit code, if it was executed."""

        err = None
        with self.suspend():
            try:
                full_cmd = shlex.split(cmd)
                full_cmd.extend(args)
                return subprocess.run(full_cmd, **kwargs).returncode
            except Exception as ex:
                err = str(ex)
        if err is not None:
            self.push_screen(StaticDialog.error("Error", err))
            return None

    @on(FileList.Open)
    def on_file_opened(self, event: FileList.Open):
        node = event.node

        if node.is_local and node.is_executable:
            # TODO: ask to confirm to run, let choose mode (on a side or in a shell)
            return

        def _open(path: str):
            if is_archive(path) and (archive_fs := open_archive(path)):
                archive_node = Node.from_path(archive_fs, "", parent=node)
                self.active_filelist.node = archive_node  # type: ignore
                self.refresh_bindings()
            else:
                open_cmd = native_open()
                if open_cmd is not None:
                    exit_code = self.subprocess_run(open_cmd, path)
                    self.app.refresh()
                    if exit_code:
                        msg = f"Application exited with an error ({exit_code})"
                        self.push_screen(StaticDialog.warning("Warning", msg))
                else:
                    self.push_screen(
                        StaticDialog.error(
                            "Error",
                            "No application found to open the file",
                        )
                    )

        def _open_temp(path: str):
            try:
                _open(path)
            finally:
                # FIXME: does it work for archives? file removed too early?
                os.unlink(path)

        if node.is_local:
            _open(node.path)
        else:
            self._download(node, cont_fn=_open_temp)

    def _download(self, node, cont_fn):
        @with_error_handler(self)
        def on_download(result: bool):
            if result:
                # FIMXE: following does not belong here:
                _, tmp_file_path = tempfile.mkstemp(
                    prefix=f"{posixpath.basename(node.path)}.",
                    suffix=posixpath.splitext(node.path)[1],
                )
                node.fs.get(node.path, tmp_file_path)
                # only this does:
                cont_fn(tmp_file_path)

        if node.is_archive:
            on_download(True)
        else:
            msg = (
                "The file is not in the local file system. "
                "It will be downloaded first. Continue?"
            )
            self.push_screen(
                StaticDialog(
                    title="Download?",
                    message=msg,
                    btn_ok="Yes",
                    btn_cancel="No",
                ),
                on_download,
            )

    def _upload(self, fs, local_path, remote_path, cont_fn):
        @with_error_handler(self)
        def on_upload(result: bool):
            if result:
                fs.put(local_path, remote_path)
            cont_fn(local_path)

        self.app.push_screen(
            StaticDialog(
                title="Upload?",
                message="The file was modified. Do you want to upload the new version?",
                btn_ok="Yes",
            ),
            on_upload,
        )

    def action_view(self):
        if not self.active_filelist:
            return
        node = self.active_filelist.cursor_node

        if not node.is_file:
            return

        def _view(path: str):
            viewer_cmd = self.config.system.viewer or default_viewer(or_editor=True)
            if viewer_cmd is not None:
                exit_code = self.subprocess_run(viewer_cmd, path)
                self.refresh()
                if exit_code:
                    msg = f"Viewer exited with an error ({exit_code})"
                    self.push_screen(StaticDialog.warning("Warning", msg))
            else:
                self.push_screen(StaticDialog.error("Error", "No viewer found!"))

        def _view_temp(path: str):
            try:
                _view(path)
            finally:
                os.unlink(path)

        if node.is_local:
            _view(node.path)
        else:
            self._download(node, cont_fn=_view_temp)

    def action_edit(self):
        if not self.active_filelist:
            return
        node = self.active_filelist.cursor_node

        if not node.is_file:
            return

        def _edit(path: str):
            editor_cmd = self.config.system.editor or default_editor()
            if editor_cmd is not None:
                exit_code = self.subprocess_run(editor_cmd, path)
                self.refresh()
                if exit_code:
                    msg = f"Editor exited with an error ({exit_code})"
                    self.push_screen(StaticDialog.warning("Warning", msg))
            else:
                self.push_screen(StaticDialog.error("Error", "No editor found!"))

        def _edit_and_upload(path: str):
            prev_mtime = Path(path).stat().st_mtime
            _edit(path)
            new_mtime = Path(path).stat().st_mtime
            if new_mtime > prev_mtime:
                self._upload(node.fs, path, node.path, cont_fn=lambda p: os.unlink(p))

        if node.is_local:
            _edit(node.path)
        else:
            self._download(node, cont_fn=_edit_and_upload)

    @work
    async def action_copy(self):
        if not self.active_filelist or not self.inactive_filelist:
            return

        if not self.active_filelist.selection:
            return

        sources = self.active_filelist.selection
        dst = self.inactive_filelist.node

        summary = sources[0].name if len(sources) == 1 else f"{len(sources)} entries"
        new_dst_path = await self.push_screen_wait(
            InputDialog(
                title=f"Copy {summary} to",
                value=dst.path,
                btn_ok="Copy",
                select_on_focus=False,
            )
        )
        if new_dst_path is None:  # user cancelled
            return

        if sources[0].fs != dst.fs and not sources[0].is_local and not dst.is_local:
            if not await self._confirm_download_upload():
                return

        overwrite = None
        for src in sources:
            overwrite = await self._copy_one(
                src.fs,
                src.path,
                dst.fs,
                new_dst_path,
                many=len(sources) > 1,
                overwrite=overwrite,
            )

        self.active_filelist.reset_selection()
        self.active_filelist.update_listing()
        self.inactive_filelist.update_listing()

    async def _confirm_download_upload(self):
        msg = (
            "Source and destination are in different remote locations.\n"
            "Continue to download, and then upload?"
        )
        return await self.app.push_screen_wait(
            StaticDialog(
                title="Download, and then upload?",
                message=msg,
                btn_ok="Yes",
                btn_cancel="No",
            )
        )

    async def _copy_one(
        self,
        src_fs,
        src: str,
        dst_fs,
        dst: str,
        many: bool,
        overwrite: Optional[bool],
    ) -> Optional[bool]:
        dst_final_path = copy_final_path(src, dst_fs, dst)
        conflict, conflict_msg, title, btn_ok = False, "", "", ""
        if src_fs.isfile(src) and dst_fs.isfile(dst_final_path):
            conflict = True
            conflict_msg = f"{dst_final_path} already exists. Overwrite?"
            title = "Overwrite?"
            btn_ok = "Overwrite"
        elif src_fs.isdir(src) and dst_fs.isdir(dst_final_path):
            conflict = True
            conflict_msg = (
                f"{dst_final_path} already exists.\n"
                "Merge directories and overwrite existing files?"
            )
            title = "Merge and overwrite?"
            btn_ok = "Merge"

        # "unpack" previous overwrite choice, if any:
        overwrite_one = overwrite if overwrite is not None else False
        overwrite_mem = overwrite is not None

        # unless user already chose to overwrite, ask every time:
        if conflict and not overwrite_mem:
            # only proopse to remember if there are many copies to perform
            if many:
                overwrite_one, overwrite_mem = await self.push_screen_wait(
                    StaticDialogR(
                        title=title,
                        message=conflict_msg,
                        btn_ok=btn_ok,
                        btn_cancel="Skip",
                        style=Style.WARNING,
                        remember="Do the same with other conflicts",
                    )
                )
            else:
                overwrite_one = await self.push_screen_wait(
                    StaticDialog(title, conflict_msg, btn_ok, style=Style.WARNING)
                )
                overwrite_mem = False

        if not conflict or conflict and overwrite_one:
            async with error_handler_async(self):
                copy(src_fs, src, dst_fs, dst)

        return overwrite_one if overwrite_mem else None

    @work
    async def action_move(self):
        if not self.active_filelist or not self.inactive_filelist:
            return

        if not self.active_filelist.selection:
            return

        sources = self.active_filelist.selection
        dst = self.inactive_filelist.node

        summary = sources[0].name if len(sources) == 1 else f"{len(sources)} entries"
        new_dst_path = await self.push_screen_wait(
            InputDialog(
                title=f"Move {summary} to",
                value=dst.path,
                btn_ok="Move",
                select_on_focus=False,
            )
        )
        if new_dst_path is None:  # user cancelled
            return

        if sources[0].fs != dst.fs and not sources[0].is_local and not dst.is_local:
            if not await self._confirm_download_upload():
                return

        overwrite = None
        for src in sources:
            overwrite = await self._move_one(
                src.fs,
                src.path,
                dst.fs,
                new_dst_path,
                many=len(sources) > 1,
                overwrite=overwrite,
            )

        self.active_filelist.reset_selection()
        self.active_filelist.update_listing()
        self.inactive_filelist.update_listing()

    async def _move_one(
        self,
        src_fs,
        src: str,
        dst_fs,
        dst: str,
        many: bool,
        overwrite: Optional[bool],
    ) -> Optional[bool]:
        dst_final_path = copy_final_path(src, dst_fs, dst)

        if src_fs.isdir(src) and dst_fs.isdir(dst_final_path):
            # Move has no merge for directories intentionally.
            # It is considered way too ambiguous and, if necessary,
            # can be achieved otherwise (copy, then delete).
            await self.push_screen_wait(
                StaticDialog(
                    title="Destination exists",
                    message=f"{dst_final_path} already exists.",
                    btn_ok=None,
                    btn_cancel="Skip" if many else "Cancel",
                    style=Style.WARNING,
                )
            )
            return overwrite  # no change

        # "unpack" previous overwrite choice, if any:
        conflict = False
        overwrite_one = overwrite if overwrite is not None else False
        overwrite_mem = overwrite is not None

        if src_fs.isfile(src) and dst_fs.isfile(dst_final_path):
            # IMPORTANT: overriding dst with the exact target **file** path
            # if not done, eventually shutil.move raises an error
            # (try shutil.move('a', 'b') where 'b' is a dir with a file 'a')
            dst = dst_final_path
            conflict = True

        if conflict and not overwrite_mem:
            msg = f"{dst_final_path} already exists. Overwrite?"
            if many:
                overwrite_one, overwrite_mem = await self.push_screen_wait(
                    StaticDialogR(
                        title="Overwrite?",
                        message=msg,
                        btn_ok="Overwrite",
                        btn_cancel="Skip",
                        style=Style.WARNING,
                        remember="Do the same with other conflicts",
                    )
                )
            else:
                overwrite_one = await self.push_screen_wait(
                    StaticDialog(
                        title="Overwrite?",
                        message=msg,
                        btn_ok="Overwrite",
                        style=Style.WARNING,
                    )
                )
                overwrite_mem = False

        if not conflict or conflict and overwrite_one:
            async with error_handler_async(self):
                move(src_fs, src, dst_fs, dst)

        return overwrite_one if overwrite_mem else None

    @work
    async def action_rename(self):
        if not self.active_filelist:
            return

        if len(self.active_filelist.selection) != 1:
            return

        node = self.active_filelist.selection[0]  # FIXME: cusror_node?
        new_name = await self.push_screen_wait(
            InputDialog(title=f"Rename {node.name} to", value=node.name, btn_ok="Move")
        )
        if new_name is None:  # user cancelled
            return

        # FIXME: only allow simple names in the first place (validation)
        if posixpath.basename(new_name) != new_name:
            await self.push_screen_wait(
                StaticDialog.error(
                    "Error",
                    "Only simple names are allowed for renaming. Otherwise, use Move.",
                )
            )
            return

        async with error_handler_async(self):
            rename(node.fs, node.path, new_name)

        self.active_filelist.reset_selection()
        self.active_filelist.update_listing()
        self.active_filelist.scroll_to_entry(new_name)

    @work
    async def action_delete(self):
        if not self.active_filelist:
            return

        if not self.active_filelist.selection:
            return

        nodes = self.active_filelist.selection
        summary = nodes[0].name if len(nodes) == 1 else f"{len(nodes)} entries"
        msg = (
            f"This will move {summary} to Trash"
            if nodes[0].is_local
            else f"This will PERMANENTLY DELETE {summary}"
        )
        confirmed = await self.push_screen_wait(
            StaticDialog(
                title="Delete?", message=msg, btn_ok="Delete", style=Style.DANGER
            )
        )
        if not confirmed:
            return

        async with error_handler_async(self):
            for node in nodes:
                delete(node.fs, node.path)

        self.active_filelist.reset_selection()
        self.active_filelist.update_listing()

    @work
    async def action_mkdir(self):
        if not self.active_filelist:
            return

        node = self.active_filelist.node

        new_name = await self.push_screen_wait(
            InputDialog("New directory", btn_ok="Create")
        )
        if new_name is None:
            return

        async with error_handler_async(self):
            mkdir(node.fs, node.path, new_name)

        self.active_filelist.update_listing()
        self.active_filelist.scroll_to_entry(new_name)

    @work
    async def action_mkfile(self):
        if not self.active_filelist:
            return

        node = self.active_filelist.node

        new_name = await self.push_screen_wait(InputDialog("New file", btn_ok="Create"))
        if new_name is None:
            return

        # FIXME: only allow simple names in the first place (validation)
        if posixpath.basename(new_name) != new_name:
            await self.push_screen_wait(
                StaticDialog.error("Error", "Only simple names are allowed")
            )
            return

        async with error_handler_async(self):
            mkfile(node.fs, node.path, new_name)

        self.active_filelist.update_listing()
        self.active_filelist.scroll_to_entry(new_name)

    def action_shell(self):
        if not self.active_filelist:
            return

        node = self.active_filelist.node
        cwd = node.path if node.is_local else Path.cwd()

        shell_cmd = self.config.system.shell or default_shell()
        if shell_cmd is not None:
            exit_code = self.subprocess_run(shell_cmd, cwd=cwd)
            self.refresh()
            self.active_filelist.update_listing()
            if self.inactive_filelist:
                self.inactive_filelist.update_listing()
            if exit_code != 0:
                msg = f"Shell exited with an error ({exit_code})"
                self.push_screen(StaticDialog.warning("Warning", msg))
        else:
            self.push_screen(StaticDialog.error("Error", "No shell found!"))

    @work
    async def action_archive(self):
        if not self.active_filelist:
            return

        if not self.active_filelist.selection:
            return

        if not self.active_filelist.node.is_local:
            await self.push_screen_wait(
                StaticDialog.info(
                    "Cannot archive",
                    "Archival is only supported in the local file system",
                )
            )
            return

        sources = self.active_filelist.selection

        summary = sources[0].name if len(sources) == 1 else f"{len(sources)} entries"
        msg = Text()
        msg.append(
            "Suported archive types: .zip, .tar.gz, .tar.bz2, .tar.xz, .7z, and more",
            style="dim",
        )
        msg.append("\n\n")
        msg.append(f"Archive {summary} to")

        active_node = self.active_filelist.node
        proposed_name = (
            posixpath.splitext(sources[0].name)[0]
            if len(sources) == 1
            else active_node.name
        )
        proposed_path = posixpath.join(active_node.path, proposed_name) + ".zip"
        output_path = await self.push_screen_wait(
            InputDialog(
                msg,
                value=proposed_path,
                btn_ok="Archive",
                select_on_focus=False,
            )
        )
        if output_path is None:
            return

        if active_node.fs.isfile(output_path):
            msg = f"{output_path} already exists. Overwrite?"
            if not await self.push_screen_wait(
                StaticDialog(
                    title="Overwrite?",
                    message=msg,
                    btn_ok="Overwrite",
                    style=Style.WARNING,
                )
            ):
                return

        async with error_handler_async(self):
            write_archive([s.path for s in sources], active_node.path, output_path)
            self.active_filelist.reset_selection()
            self.active_filelist.update_listing()
            self.active_filelist.scroll_to_entry(posixpath.basename(output_path))

    def _on_go_to(self, location: Union[str, FileSystem, None]):
        if location is None:
            return

        if not self.active_filelist:
            return

        if isinstance(location, str):
            try:
                node = Node.from_url(location)
                err_msg = f"{location} is not a directory" if not node.is_dir else None
            except Exception as err:
                node = None
                err_msg = str(err)

            if node and node.is_dir:
                self.active_filelist.node = node
            else:
                self.push_screen(
                    StaticDialog.info(f"Cannot navigate to {location}", err_msg)
                )

        if isinstance(location, FileSystem):
            protocol = location.protocol
            path = location.path
            fs = fsspec.filesystem(protocol, **location.params)
            node = Node.from_path(fs, path or "/")
            self.active_filelist.node = node

    @work
    async def action_go_to_bookmark(self):
        location = await self.app.push_screen_wait(GoToBookmarkDialog())
        async with error_handler_async(self):
            self._on_go_to(location)

    @work
    async def action_go_to_path(self):
        if not self.active_filelist:
            return

        location = await self.push_screen_wait(
            InputDialog("Jump to...", value=self.active_filelist.node.path, btn_ok="Go")
        )
        async with error_handler_async(self):
            self._on_go_to(location)

    @work
    async def action_navigate_to_config(self):
        async with error_handler_async(self):
            self._on_go_to(str(config_root()))

    @work
    async def action_connect(self):
        if not self.active_filelist:
            return

        connection_params = await self.push_screen_wait(ConnectToRemoteDialog())
        if connection_params is None:
            return

        async with error_handler_async(self):
            protocol, path, fs_args = connection_params
            remote_fs = fsspec.filesystem(protocol, **fs_args)
            node = Node.from_path(remote_fs, path or "/")
            self.active_filelist.node = node

    @work
    async def action_quit(self):
        if self.config.system.ask_before_quit:
            confirmed, remember = await self.push_screen_wait(
                StaticDialogR(title="Quit?", remember="Don't ask again")
            )
            if confirmed and remember:
                with self.config.autosave() as config:
                    config.system.ask_before_quit = False
            if confirmed:
                self.exit()
        else:
            self.exit()

    @work
    async def action_configure(self):
        await self.push_screen_wait(ConfigDialog())

    @work
    async def action_check_for_updates(self, auto=False):
        # avoid checking too frequently:
        one_day = 1 * 24 * 60 * 60
        since_last_check = time.time() - self.config.startup.last_update_check_time
        if auto and since_last_check < one_day:
            return

        # try getting the versions:
        try:
            current, latest = check_for_updates()
        except Exception as ex:
            if not auto:
                await self.push_screen_wait(
                    StaticDialog.warning("Update check failed", str(ex))
                )
            return

        if latest > current:
            already_notified = latest == self.config.startup.last_update_check_version

            if auto and already_notified:
                # do not notify about the same version more than once
                pass
            else:
                title = "A newer version is available"
                msg = (
                    f"An update is available: {current} -> {latest}.\n"
                    "To update, run `pipx upgrade f2-commander` or an equivalent."
                )
                await self.push_screen_wait(StaticDialog.info(title, msg))

        elif not auto:
            title = "Up to date!"
            msg = f"You are currently using the latest version: {current}"
            await self.push_screen_wait(StaticDialog.info(title, msg))

        with self.config.autosave() as config:
            config.startup.last_update_check_time = int(time.time())
            config.startup.last_update_check_version = str(latest)

    @work
    async def action_about(self):
        title = f"F2 Commander {version('f2-commander')}"
        msg = (
            'This application is provided "as is", without warranty of any kind.\n'
            "This application is licensed under the Mozilla Public License, v. 2.0.\n"
            "You can find a copy of the license at https://mozilla.org/MPL/2.0/"
        )
        await self.push_screen_wait(StaticDialog.info(title, msg))
        with self.config.autosave() as conf:
            conf.startup.license_accepted = True

    def action_help(self):
        self.panel_left.panel_type = "help"

    def check_action(self, action, parameters):
        if self.active_filelist and self.active_filelist.node.is_archive:
            if action in ("move", "delete", "mkfile", "mkdir", "edit"):
                return None  # visible, but disabled
            else:
                return True
        else:
            return True
