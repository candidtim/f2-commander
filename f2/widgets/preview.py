# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import io
import math
import posixpath
import shutil
from typing import Optional, Tuple, Union

import pymupdf
from fsspec import filesystem
from PIL import Image as PillowImage
from rich.syntax import Syntax
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import LoadingIndicator, Static
from textual_image._terminal import get_cell_size
from textual_image.widget import Image as TextualImage

from f2.fs.arch import open_archive
from f2.fs.node import Node
from f2.fs.util import (
    breadth_first_walk,
    is_image_file,
    is_pdf_file,
    is_text_file,
    shorten,
)


class Preview(Static):
    DEFAULT_CSS = """
    #preview-container {
        align: center middle;
    }

    #image-preview {
        padding: 1;
    }

    #text-preview {
        width: 100%;
        height: 100%;
    }
    """
    # FIXME: use "real" image size, only dezoom when need to fit

    node = reactive(Node.cwd())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._preview_content = None
        self._fs = filesystem("file")

    def compose(self) -> ComposeResult:
        with Horizontal(id="preview-container"):
            yield LoadingIndicator(id="loading-indicator")
            yield TextualImage(None, id="image-preview")
            yield Static("", id="text-preview")

    def on_mount(self):
        self.node = self.app.active_filelist.cursor_node

    # FIXME: push_message (in)directy to the "other" panel only?
    def on_other_panel_selected(self, node: Node):
        self.node = node

    @work(exclusive=True, thread=True)
    async def watch_node(self, old: Node, new: Node):
        parent: Widget = self.parent  # type: ignore
        loading_indicator = self.query_one("#loading-indicator")
        image_preview = self.query_one("#image-preview")
        text_preview = self.query_one("#text-preview")

        # set title:
        parent.border_title = shorten(
            new.path, width_target=self.size.width, method="slice"
        )
        parent.border_subtitle = None

        # update content:
        loading_indicator.remove_class("hidden")
        text, image = await self._format(self.node)
        loading_indicator.add_class("hidden")
        self._preview_content = text if text is not None else image

        if text is not None:
            text_preview.update(text)
            text_preview.remove_class("hidden")
        else:
            text_preview.update("")
            text_preview.add_class("hidden")

        if image is not None:
            self.set_preview_image(image_preview, image)
            image_preview.remove_class("hidden")
        else:
            self.unset_preview_image(image_preview)
            image_preview.add_class("hidden")

    def set_preview_image(self, image_preview, image):
        image_preview.image = image
        cell_size = get_cell_size()
        width = math.floor(image.width / cell_size.width)
        height = math.floor(image.height / cell_size.height)
        container = self.content_size
        if width > container.width:
            image_preview.styles.width = container.width
            image_preview.styles.height = "auto"
        elif height > container.height:
            image_preview.styles.width = "auto"
            image_preview.styles.height = container.height
        else:
            image_preview.styles.width = width
            image_preview.styles.height = height

    def unset_preview_image(self, image_preview):
        image_preview.image = None
        image_preview.styles.width = "auto"
        image_preview.styles.height = "auto"
        image_preview.add_class("hidden")

    async def _format(
        self, node: Node
    ) -> Tuple[Union[None, str, Syntax], Optional[PillowImage.Image]]:
        if node is None:
            return None, None

        elif node.is_dir:
            return self._dir_tree(node), None

        elif node.is_archive and node.is_local:
            archive_fs = open_archive(node.path)
            archive_node = Node.from_path(archive_fs, "")
            return self._dir_tree(archive_node), None

        elif node.is_file and is_text_file(node.path):
            try:
                return (
                    Syntax(
                        code=self._head(node),
                        lexer=Syntax.guess_lexer(node.path),
                        theme=self._syntax_theme(),
                    ),
                    None,
                )
            except UnicodeDecodeError:
                return "Cannot preview: text file cannot be read", None

        elif node.is_file and is_image_file(node.path):
            try:
                return None, PillowImage.open(self.node.path)
            except OSError:
                return "Cannot preview: image file cannot be read", None

        elif node.is_file and is_pdf_file(node.path):
            try:
                doc = pymupdf.open(node.path)
                page = doc[0]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))  # zoom for quality
                img_data = pix.tobytes("png")
                return None, PillowImage.open(io.BytesIO(img_data))
            except Exception:
                return "Cannot preview: PDF file cannot be read", None

        else:
            # TODO: leave a user a possibility to force the preview?
            return "Cannot preview: not a text or an image file", None

    def _syntax_theme(self):
        mapping = {
            "catppuccin-latte": "xcode",
            "catppuccin-mocha": "github-dark",
            "flexoki": "ansi_dark",
            "gruvbox": "gruvbox-dark",
            "textual-ansi": "ansi_light",
            "textual-dark": "ansi_dark",
            "textual-light": "default",
            "tokyo-night": "github-dark",
        }
        return mapping.get(self.app.theme, self.app.theme)

    @property
    def _height(self):
        """Viewport is not higher than this number of lines"""
        # FIXME: use Textual API instead?
        return shutil.get_terminal_size(fallback=(200, 80))[1]

    def _head(self, node: Node) -> str:
        lines = []
        with node.fs.open(node.path, "r") as f:
            try:
                for _ in range(self._height):
                    lines.append(next(f))
            except StopIteration:
                pass
        return "".join(lines)

    def _dir_tree(self, node: Node) -> str:
        """To give a best possible overview of a directory, show it traversed
        breadth-first. Some directories may not be walked in a latter case, but
        top-level will be shown first, then the second level exapnded, and so on
        recursively as long as the output fits the screen."""

        # collect paths to show, breadth-first, but at most a screenful:
        collected_paths = []  # type: ignore
        for i, p in enumerate(
            breadth_first_walk(node.fs, node.path, self.app.config.display.show_hidden)
        ):
            if i > self._height:
                break
            if posixpath.dirname(p) in collected_paths:
                siblings = [
                    e
                    for e in collected_paths
                    if posixpath.dirname(e) == posixpath.dirname(p)
                ]
                insert_at = (
                    collected_paths.index(posixpath.dirname(p)) + len(siblings) + 1
                )
                collected_paths.insert(insert_at, p)
            else:
                collected_paths.append(p)

        # format paths:
        lines = [node.path]
        for p in collected_paths:
            name = posixpath.relpath(p, node.path)
            if self._fs.isdir(p):
                name += "/"
            lines.append(f"┣ {name}")
        return "\n".join(lines)
