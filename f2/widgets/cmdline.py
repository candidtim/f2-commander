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
from textual.widgets import Static

from f2.shell import default_shell

"""
TODO:
- resize when parent resizes
- bi-directional cwd follow (from panel to cmd line and reverse)
"""


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


class RichScreen:
    """A Rich renederable for `pyte.Screen`."""

    def __init__(self, columns, lines, height):
        self.clear(columns, lines)
        self.height = height
        self.focused = False

    def clear(self, columns, lines):
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.ByteStream(self.screen)
        self.output = [Text("") for _ in range(lines)]

    def update(self, data: bytes):
        """Feed more data into from the shell output."""
        self.stream.feed(data)
        for line_number, line in enumerate(self.screen.display):
            rich_line = Text.from_ansi(line)
            if self.focused and self.screen.cursor.y == line_number:
                rich_line = self._highlight_cursor(rich_line, self.screen.cursor.x)
            self.output[line_number] = rich_line

    def focus(self):
        self.focused = True
        cursor = self.screen.cursor
        line = Text.from_ansi(self.screen.display[cursor.y])
        self.output[cursor.y] = self._highlight_cursor(line, cursor.x)

    def blur(self):
        self.focused = False
        cursor = self.screen.cursor
        line = Text.from_ansi(self.screen.display[cursor.y])
        self.output[cursor.y] = line

    @classmethod
    def _highlight_cursor(cls, line: Text, pos: int) -> Text:
        line.stylize("reverse", pos, pos + 1)
        return line

    def __rich_console__(self, console, options):
        if self.height < len(self.output):
            non_empty = [line for line in self.output if len(line.plain.strip()) > 0]
            return non_empty[-self.height :]
        else:
            return self.output


class CmdLine(Static, can_focus=True):
    def __init__(self, columns, lines):
        super().__init__()
        self.columns = columns
        self.lines = lines
        self.fd = None
        self.pipe = None
        self.renderable = RichScreen(self.columns, self.lines, height=1)

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
        os.unsetenv("LS_COLORS")  # TERM=linux has colors, hinting to disable
        os.unsetenv("COLORTERM")
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
        self.resize()

    def tear_down_io(self):
        loop = asyncio.get_running_loop()
        loop.remove_reader(self.pipe)

    def resize(self):
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
        if event.key == "ctrl+o":
            self.toggle_size()
        elif event.character is not None:
            event.stop()
            self.send_input(event.character)
        elif event.key in CONTROL_KEYS:
            event.stop()
            self.send_input(CONTROL_KEYS[event.key])

    def on_focus(self):
        self.renderable.focus()
        self.update(self.renderable)

    def on_blur(self):
        self.renderable.blur()
        self.update(self.renderable)

    # def on_resize(self, event):
    #     # FIXME: duplicate code from `F2Commander.compose`
    #     self.columns = self.app.size.width
    #     self.lines = self.app.size.height
    #     self.renderable.clear(self.columns, self.lines)
    #     self.resize()

    def toggle_size(self):
        if self.renderable.height == 1:
            self.renderable.height = self.lines
        else:
            self.renderable.height = 1
        self.refresh(layout=True)

    def chdir(self, path):
        # disable echo:
        old_attrs = termios.tcgetattr(self.fd)
        new_attrs = old_attrs[:]
        new_attrs[3] &= ~termios.ECHO
        termios.tcsetattr(self.fd, termios.TCSANOW, new_attrs)
        # cd:
        self.pipe.write(f"cd {path}\n".encode())
        # enable echo:
        termios.tcsetattr(self.fd, termios.TCSANOW, old_attrs)
