# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2025 Timur Rubeko

import asyncio
import fcntl
import os
import pty
import struct
import termios
from functools import lru_cache
from typing import Iterator, Tuple

import pyte
from rich.style import Style
from rich.text import Text
from textual.widgets import Static

from f2.shell import default_shell

# Control sequences related to user input for TERM=linux
# Obtained with `infocmp -L linux | grep key`
CONTROL_KEYS = {
    "f1": "\x1b[[A",
    "f2": "\x1b[[B",
    "f3": "\x1b[[C",
    "f4": "\x1b[[D",
    "f5": "\x1b[[E",
    "f6": "\x1b[17~",
    "f7": "\x1b[18~",
    "f8": "\x1b[19~",
    "f9": "\x1b[20~",
    "f10": "\x1b[21~",
    "f11": "\x1b[23~",
    "f12": "\x1b[24~",
    "f13": "\x1b[25~",
    "f14": "\x1b[26~",
    "f15": "\x1b[28~",
    "f16": "\x1b[29~",
    "f17": "\x1b[31~",
    "f18": "\x1b[32~",
    "f19": "\x1b[33~",
    "f20": "\x1b[34~",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "right": "\x1b[C",
    "left": "\x1b[D",
    "home": "\x1b[1~",
    "insert": "\x1b[2~",
    "delete": "\x1b[3~",
    "end": "\x1b[4~",
    "pageup": "\x1b[5~",
    "pagedown": "\x1b[6~",
}

ANSI_COLORS = set(["black", "red", "green", "blue", "magenta", "cyan", "white"])


class RichScreen:
    """A Rich renederable for `pyte.Screen`."""

    def __init__(self, columns, lines, height, theme):
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.ByteStream(self.screen)
        self.output = [Text("") for _ in range(lines)]
        self.cursor_line = 0
        self.height = height
        self.focused = False
        self.theme = theme

    def update(self, data: bytes):
        """Feed more data into from the shell output."""
        self.stream.feed(data)

        if len(self.screen.dirty) > self.screen.lines * 0.2:
            # too many changes, refresh the full screen:
            updated_output = []
            for line_number in range(self.screen.lines):
                rich_line = self._render_line(line_number)
                updated_output.append(rich_line)
        else:
            # only update changed lines:
            updated_output = self.output[:]
            for line_number in self.screen.dirty | {
                self.cursor_line,
                self.screen.cursor.y,
            }:
                rich_line = self._render_line(line_number)
                updated_output[line_number] = rich_line
        self.output = updated_output
        self.screen.dirty.clear()
        self.cursor_line = self.screen.cursor.y

    def _render_line(self, line_number: int) -> Text:
        # FIXME: review for performance improvements
        pyte_line = self.screen.buffer[line_number]
        rich_line = Text()
        style_start, rich_style, pyte_style = None, None, None
        for i in range(self.screen.columns):
            char = pyte_line[i]
            rich_line.append(char.data)
            new_pyte_style = (
                char.fg,
                char.bg,
                char.bold,
                char.italics,
                char.underscore,
                char.strikethrough,
                char.blink,
            )
            if pyte_style != new_pyte_style:
                if rich_style is not None:
                    rich_line.stylize(rich_style, style_start, i)
                style_start = i
                rich_style = self._to_rich_style(*new_pyte_style)
                pyte_style = new_pyte_style
        rich_line.stylize(rich_style, style_start, i)
        cursor = self.screen.cursor
        if self.focused and cursor.y == line_number:
            rich_line.stylize("reverse", cursor.x, cursor.x + 1)
        return rich_line

    @lru_cache(maxsize=4096)
    def _to_rich_style(
        self,
        fg: str,
        bg: str,
        bold: bool,
        italics: bool,
        underscore: bool,
        strikethrough: bool,
        blink: bool,
    ) -> Style:
        return Style(
            color=self._to_rich_color(fg, True),
            bgcolor=self._to_rich_color(bg, False),
            bold=bold,
            italic=italics,
            underline=underscore,
            strike=strikethrough,
            blink=blink,
        )

    @lru_cache(maxsize=1024)
    def _to_rich_color(self, pyte_color: str, fg: bool) -> str:
        if pyte_color == "default" and fg:
            return self.theme.foreground
        elif pyte_color == "default" and not fg:
            return self.theme.background
        elif pyte_color == "brown":
            return "yellow"
        elif pyte_color in ANSI_COLORS:
            return pyte_color
        else:
            return f"#{pyte_color}"

    def resize(self, columns, lines, height):
        self.screen.resize(lines, columns)
        self.screen.ensure_hbounds()
        self.screen.ensure_vbounds()
        self.height = height
        self.update(b"")

    def focus(self):
        self.focused = True
        cursor = self.screen.cursor
        line = self._render_line(cursor.y)
        line.stylize("reverse", cursor.x, cursor.x + 1)
        self.output[cursor.y] = line

    def blur(self):
        self.focused = False
        cursor = self.screen.cursor
        line = self._render_line(cursor.y)
        self.output[cursor.y] = line

    def __rich_console__(self, console, options):
        if self.height < len(self.output):
            non_empty = [line for line in self.output if len(line.plain.strip()) > 0]
            return non_empty[-self.height :]
        else:
            return self.output


class CmdLine(Static, can_focus=True):
    def __init__(self):
        super().__init__()
        self.columns = self._max_width()
        self.lines = self._max_height()
        self.fd = None
        self.pipe = None
        self.renderable = RichScreen(
            self.columns, self.lines, self.size.height, self.app.theme_
        )

    def on_mount(self):
        self.start()

    #
    # Fork:
    #

    def start(self):
        """Start the termainal emulator."""
        pid, self.fd = pty.fork()
        if pid == 0:
            # in the forked process:
            self.start_shell()
        else:
            # in the main process:
            self.setup_io()

    def restart(self):
        self.tear_down_io()
        self.start()

    def start_shell(self):
        """Start a shell in a forked process."""
        # see `self._resize`, but just in case:
        os.environ["COLUMNS"] = f"{self.columns}"
        os.environ["LINES"] = f"{self.lines}"
        # avoid encoding surprises:
        os.environ["LC_ALL"] = "en_US.UTF-8"
        # dumbify:
        # ( see also: https://www.man7.org/linux/man-pages/man7/term.7.html )
        os.environ["TERM"] = "linux"  # simplest and most generic among PC consoles
        # replace the executable by a new interactive shell, inherit env:
        shell_cmd = self.app.config.system.shell or default_shell()
        os.execlp(shell_cmd, shell_cmd)

    #
    # IO with a forked process:
    #

    def setup_io(self):
        # prepare the pipe for stdin-stdout/err and start reading the output:
        self.pipe = os.fdopen(self.fd, "w+b", 0)
        loop = asyncio.get_running_loop()
        loop.add_reader(self.pipe, self.read_output)
        # set the screen size:
        self.resize_terminal()

    def tear_down_io(self):
        loop = asyncio.get_running_loop()
        loop.remove_reader(self.pipe)

    def resize_terminal(self):
        winsize = struct.pack("HHHH", self.lines, self.columns, 0, 0)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

    def read_output(self):
        try:
            shell_output = self.pipe.read(self.lines * self.columns)
            self.renderable.update(shell_output)
            self.update(self.renderable)
        except OSError:
            self.restart()

    def send_input(self, s: str):
        try:
            self.pipe.write(s.encode())
        except OSError:
            self.restart()

    #
    # Textual event processing:
    #

    def on_key(self, event):
        # let the app handle some keys:
        bubble_up = ("ctrl+o", "ctrl+z", "shift+tab")
        if event.key in bubble_up:
            return

        event.stop()

        # CmdLine specific key bindings:
        if event.key == "ctrl+f":
            self.send_input(self.app.last_active_filelist.node.path)
        elif event.key == "ctrl+end":
            self.send_input(self.app.last_active_filelist.cursor_node.name)
        elif event.key == "ctrl+shift+end":
            self.send_input(self.app.last_active_filelist.cursor_node.path)

        # all else is passed to the command line, if possible:
        elif event.key in CONTROL_KEYS:
            self.send_input(CONTROL_KEYS[event.key])
        elif event.character is not None:
            self.send_input(event.character)

    def on_focus(self):
        self.renderable.focus()
        self.update(self.renderable)

    def on_blur(self):
        self.renderable.blur()
        self.update(self.renderable)

    def on_resize(self, event):
        # adjust built-in terminal size to the app size, if changed:
        if self.columns != self._max_width() or self.lines != self._max_height():
            self.columns = self._max_width()
            self.lines = self._max_height()
            self.resize_terminal()
        # render as many last lines as currently visible:
        self.renderable.resize(self.columns, self.lines, self.size.height)
        self.update(self.renderable)

    def _max_width(self):
        return self.app.size.width - 2  # border left, border right

    def _max_height(self):
        return self.app.size.height - 3  # border top, border bottom, footer
