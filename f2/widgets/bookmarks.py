# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

from pathlib import Path
from typing import Union
from urllib.parse import urlparse

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList
from textual.widgets.option_list import Option

from f2.config import FileSystem

from .types import WithF2App


class GoToBookmarkDialog(ModalScreen[Union[str, FileSystem, None]], WithF2App):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("backspace", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def __init__(self):
        super().__init__()
        options = [
            self._url_to_option(idx, url)
            for idx, url in enumerate(self.app_.config.bookmarks.paths)
        ]
        if self.app_.config.file_systems:
            options.append(None)  # type: ignore (docs allow None for a separator)
            options.append(Option("Remote file systems:", disabled=True))
            options.extend(
                [
                    self._remote_fs_to_option(fs_conf)
                    for fs_conf in self.app_.config.file_systems
                ]
            )
        self.option_list = OptionList(*options, id="options")

    def _url_to_option(self, idx: int, url: str) -> Option:
        prefix = (f"[{idx}]", "grey50") if idx in range(1, 10) else "   "
        # validate local paths, but allow all URLs (won't connect to validate them):
        is_url = urlparse(url).scheme != ""
        is_dir = Path(url).expanduser().is_dir() if not is_url else False
        return Option(
            Text.assemble(prefix, " ", url),
            disabled=not is_url and not is_dir,
        )

    def _remote_fs_to_option(self, fs_conf: FileSystem) -> Option:
        prefix = (" - ", "grey50")
        return Option(
            Text.assemble(prefix, " ", fs_conf.display_name),
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Go to a bookmark", id="title")
            yield self.option_list
            with Horizontal(id="buttons"):
                yield Button("Cancel", variant="default", id="cancel")

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    @on(OptionList.OptionSelected)
    def on_select_changed(self, event: OptionList.OptionSelected) -> None:
        self.on_index_selected(event.option_index)

    def on_key(self, event: events.Key) -> None:
        if event.key in [str(i) for i in range(1, 10)]:
            # FIXME: do not allow disabled indices to be selected
            idx = int(event.key)
            self.on_index_selected(idx)
        elif event.key == "j":
            self.option_list.action_cursor_down()
        elif event.key == "k":
            self.option_list.action_cursor_up()

    def on_index_selected(self, idx):
        if idx < len(self.app_.config.bookmarks.paths):
            value = self.app_.config.bookmarks.paths[idx]
            self.dismiss(value)
        else:
            fs_conf = self.app_.config.file_systems[
                idx - len(self.app_.config.bookmarks.paths) - 1
            ]
            self.dismiss(fs_conf)
