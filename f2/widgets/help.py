# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko


from importlib.metadata import version

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import MarkdownViewer, Static

from ..config import user_config_path

# FIXME: big potion of this message needs to be in sink
#        with the bindings -> generate it automatically


HELP = f"""
# F2 Commander {version('f2-commander')}

> Presse any key to close this panel

## Usage

### Interface

 - `Tab`: switch focus between the left and right panels
 - `Ctrl+p`: open the command palette
 - `Ctrl+w`: swap the panels
 - `Ctrl+s`: open the same location in the other panel
 - `Ctrl+e`: change the type of the panel on the *left*
 - `Ctrl+r`: change the type of the panel on the *right*
 - `?`: show this help
 - `q`: quit the application
 - Keys shown in the footer execute the indicated actions

### Navigation

 - `j`/`k` and `up`/`down`: navigate the list up and down one entry at a time
 - `g`: navigate to the *top* of the list
 - `G`: navigate to the *bottom* of the list
 - `Ctrl+f`/`Ctrl+b`, `Ctrl+d`/`Ctrl+u`, `Page Up`/`Page Down`: paginate the list
 - `Enter`: enter the directory or run the default program associated with a
    file type under cursor
 - `b`/`Backspace` or `Enter` on the `..` entry: navigate up in a directory tree
 - `R`: refresh the file listing
 - `o`: open the current location in the deafult OS file manager

### Controlling the displayed items

 - `h`: show/hide hidden files
 - `n`/`N`: order the entries by name
 - `s`/`S`: order the entries by size
 - `t`/`T`: order the entries by last modification time
 - `f`: filter the displayed entries with a glob expression

### Selection

 - `Space`: select/unselect an entry under the cursor
 - `-`: clear selection
 - `+`: select all displayed entries
 - `*`: invert selection

### Shell

 - `x` starts (forks) a subprocess with a new shell in the current location.
   Quit the shell to return back to the F2 Commander (e.g., `Ctrl+d` or type and
   execute `exit`).

### Options

These toggles can be found in Command Palette:

 - Show directories first, on/off
 - Case-sensitive name ordering, on/off

## Configuration

Your configuration file is:

    {str(user_config_path())}

Use `Ctrl+g` to navigate to it.

Configuration file is a simple list of key-value pairs, similar to how variables are
declared in Bash. The syntax is that of `.env` files and is described in more details
in https://saurabh-kumar.com/python-dotenv/#file-format . Allowed values are Python
primitives: strings, numbers and boolean `True` or `False` (capitalized). Values can be
quoted.

The application may too write to the configuration file (e.g., when you change the
settings within the application itself), but will attempt to preserve its formatting.

## License

This application is provided "as is", without warranty of any kind.
This application is licensed under the Mozilla Public License, v. 2.0.
You can find a copy of the license at https://mozilla.org/MPL/2.0/
"""


class Help(Static):
    def compose(self) -> ComposeResult:
        parent: Widget = self.parent  # type: ignore
        parent.border_title = "Help"
        parent.border_subtitle = None
        yield MarkdownViewer(HELP, show_table_of_contents=False)

    def on_key(self, event) -> None:
        event.stop()
        self.parent.panel_type = "file_list"  # type: ignore
