# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

from pathlib import Path

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class Preview(Static):
    preview_path = reactive(Path.cwd(), recompose=True)

    def compose(self) -> ComposeResult:
        content = ""
        if self.preview_path is not None:
            content = str(self.preview_path)
        yield Static(content)

    # FIXME: push_message (in)directy to the "other" panel?
    def on_other_panel_selected(self, path: Path):
        self.preview_path = path

    def watch_preview_path(self, old: Path, new: Path):
        parent: Widget = self.parent  # type: ignore
        parent.border_title = str(new)
        parent.border_subtitle = None
