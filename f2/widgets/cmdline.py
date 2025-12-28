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

import pyte
from rich.text import Text
from textual import work
from textual.widgets import Static

from f2.shell import default_shell

"""
TODO:
    - restart if forked process ends
    - do not focus with Tab
    - resize when parent resizes
    - bi-directional cwd follow (from panel to cmd line and reverse)
    - disable command palette in CmdLine widget to allow using ctrl+p
    - allow using arrow keys
    - do not render cursor if the widget is not focused
"""


# TODO: improve rendering performance
# For performance reasons, embedded terminal is limited in size
# Empirically, anything above ~4KB (e.g., 120x40) gets way too slow
MAX_COLUMNS = 80
MAX_LINES = 24


class RichScreen:
    """A Rich renederable for `pyte.Screen`."""

    def __init__(self, columns, lines, height):
        self.clear(columns, lines)
        self.height = height

    def clear(self, columns, lines):
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.ByteStream(self.screen)
        self.output = [""] * lines

    def update(self, data: bytes):
        self.stream.feed(data)
        for line_number in self.screen.dirty:
            raw_line = self.screen.display[line_number]
            rich_line = Text.from_ansi(raw_line)
            # highlight cursor:
            if self.screen.cursor.y == line_number:
                pos = self.screen.cursor.x
                rich_line.stylize("reverse", pos, pos + 1)
            self.output[line_number] = rich_line

    def __rich_console__(self, console, options):
        if self.height < len(self.output):
            non_empty = [line for line in self.output if len(line.plain.strip()) > 0]
            return non_empty[-self.height :]
        else:
            return self.output


class CmdLine(Static, can_focus=True):
    def __init__(self, columns, lines):
        super().__init__()
        self.columns = min(columns, MAX_COLUMNS)
        self.lines = min(lines, MAX_LINES)
        self.fd = None
        self.pipe = None
        self.renderable = RichScreen(self.columns, self.lines, height=1)

    def on_mount(self):
        pid, self.fd = pty.fork()
        if pid == 0:
            # in the forked process:
            self.start_shell()
        else:
            # in the main process:
            self.on_fork()

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
        os.unsetenv("LS_COLORS")  # TERM=linux has colors, hinting to disable
        os.unsetenv("COLORTERM")
        # replace the executable by a new interactive shell, inherit env:
        shell_cmd = self.app.config.system.shell or default_shell()
        os.execlp(shell_cmd, shell_cmd)

    def on_fork(self):
        # prepare the pipe for stdin-stdout/err and start reading the output:
        self.pipe = os.fdopen(self.fd, "w+b", 0)
        loop = asyncio.get_running_loop()
        loop.add_reader(self.pipe, self.update_output)
        # set the screen size:
        self._resize()

    def _resize(self):
        winsize = struct.pack("HHHH", self.lines, self.columns, 0, 0)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

    def _chdir(self, path):
        # disable echo:
        old_attrs = termios.tcgetattr(self.fd)
        new_attrs = old_attrs[:]
        new_attrs[3] &= ~termios.ECHO
        termios.tcsetattr(self.fd, termios.TCSANOW, new_attrs)
        # cd:
        self.pipe.write(f"cd {path}\n".encode())
        # enable echo:
        termios.tcsetattr(self.fd, termios.TCSANOW, old_attrs)

    def on_key(self, event):
        if event.key == "ctrl+o":
            self.toggle()

        elif event.key == "tab":
            # FIXME: better API to "focus next""?
            # FIXME: allow tab, find another hotkey to focus out
            self.app.left.focus()

        elif event.character is not None:
            event.stop()
            self.pipe.write(event.character.encode())

        # TODO: need to restart reliably (implementation below does not work)
        # except OSError:
        #     self.refresh(recompose=True)

    def update_output(self):
        # TODO: process OSError:
        shell_output = self.pipe.read(self.lines * self.columns)
        self.renderable.update(shell_output)
        self.update(self.renderable)

    def toggle(self):
        if self.renderable.height == 1:
            self.renderable.height = self.lines
        else:
            self.renderable.height = 1
        self.refresh(layout=True)

    # def on_resize(self, event):
    #     # FIXME: duplicate code from `F2Commander.compose`
    #     self.columns = min(self.app.size.width, MAX_COLUMNS)
    #     self.lines = min(self.app.size.height // 2, MAX_LINES)
    #     self.renderable.clear(self.columns, self.lines)
    #     self._resize()
