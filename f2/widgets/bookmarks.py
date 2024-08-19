# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

from pathlib import Path

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList
from textual.widgets.option_list import Option

from ..config import config


class GoToBookmarkDialog(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("backspace", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def __init__(self):
        super().__init__()
        options = [
            self._to_option(idx, path) for idx, path in enumerate(config.bookmarks)
        ]
        self.option_list = OptionList(*options, id="options")

    def _to_option(self, idx: int, path: str) -> Option:
        prefix = (f"[{idx}]", "grey50") if idx in range(1, 10) else "   "
        return Option(
            Text.assemble(prefix, " ", path),  # type: ignore
            disabled=self._dir_path(path) is None,
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
            idx = int(event.key)
            self.on_index_selected(idx)
        elif event.key == "j":
            self.option_list.action_cursor_down()
        elif event.key == "k":
            self.option_list.action_cursor_up()

    def on_index_selected(self, idx):
        value = config.bookmarks[idx]
        path_or_nothing = self._dir_path(value)
        self.dismiss(path_or_nothing)

    def _dir_path(self, maybe_dir_path: str) -> Path | None:
        """Attempt to resolve the provided directory path, or return None"""
        path = Path(maybe_dir_path)
        if "~" in maybe_dir_path:
            path = path.expanduser()
        return path if path.is_dir() else None
