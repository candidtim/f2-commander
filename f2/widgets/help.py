# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko


from importlib.metadata import version

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import MarkdownViewer, Static

from f2.config import user_config_path

# FIXME: big potion of this message needs to be in sink
#        with the bindings -> generate it automatically


HELP = f"""
# F2 Commander {version("f2-commander")}

> Press `Esc`, `q`, or `Backspace` to exit this help

> Press `t` to toggle the table of contents

## Quick start

 - `Tab ⭾` switches focus between the left and right panels
 - `j`/`k` and `⇧`/`⇩` navigate the file list up and down, one entry at a time
 - `Enter ⮐` enters the directory or opens the file with the system default program
 - `Backspace ⌫` (or `Enter ⮐` on the `..`) navigates to the parent directory
 - All keys shown in the footer execute the indicated actions (copy, move, etc.)
 - `Ctrl+p` opens the Command Palette
 - `q`/`F10` (as shown in the footer) quits the application

## Basic usage

### Navigation

 - `Tab ⭾` switches focus between the left and right panels
 - `j`/`k` and `⇧`/`⇩` navigate the file list up and down, one entry at a time
 - `g`/`Home` navigates to the top of the list
 - `G`/`End` navigates to the bottom of the list
 - `Ctrl+f`/`Ctrl+b`, `Page Down`/`Page Up` scroll a page down and up
 - `Ctrl+d`/`Ctrl+u` scroll half a page down and up
 - `Enter ⮐` enters the directory or opens the file with the system default program
 - `Backspace ⌫` (or `Enter ⮐` on the `..`) navigates to the parent directory
 - `b`/`F2` go to a bookmarked location (bookmarks are configurable)
 - `Ctrl+g` enter a path to jump to
 - `/` incremental fuzzy search in the list
 - `R` refresh the file listing
 - `o` open the current location in the default OS file manager
 - `Ctrl+w` swap the panels
 - `Ctrl+s` open the same location in the other panel

### Display control

 - `h` toggle the display of hidden files
 - `n`/`N` order the entries by name
 - `s`/`S` order the entries by size
 - `t`/`T` order the entries by last modification time
 - `Ctrl+Space` calculate the size of the directory under cursor

### File manipulation

Most actions for file and directory manipulation are shown in the footer menu.
A few more actions are available in the Command Palette (`Ctrl+p`).

Depending on your configuration, key bindings are either the mnemonics for the actions:

  - `c` copy
  - `m` move
  - `D` delete (upper case `D`)
  - etc.

or use the traditional Function keys:

  - `F5` copy
  - `F6` move
  - `F8` delete
  - etc.

Current mapping is shown in the footer menu. The mapping (Vi-like or Fn-keys) can be
changed in the Configuration (`Ctrl+p` -> "Configuration").

### Multiple selection

Some actions, such as copy, move and delete, can be performed on multiple entries.

 - `Space` or `Shift`+`j`/`k`/`⇧`/`⇩` select/unselect an entry under the cursor
 - `-` clears the selection
 - `+` selects all displayed entries
 - `*` inverts the selection

### Shell

 - `x`/`F9` starts (forks) a subprocess with a new shell in the current location.
   Quit the shell to return back to the F2 Commander (e.g., `Ctrl+d` or type and
   execute `exit`).

## Remote (FTP, S3, etc.)

 - `Ctrl+t` opens a dialog to connect to a remote file system

Remote file systems support is in "preview" mode. Most functionality is available,
but bugs are possible.

To connect to a remote file system you may need to **install additional packages**
that are indicated in the "Connect" dialog upon selecting a protocol.

For example, if you installed F2 Commander with `pipx`, and you want to connect
to an S3 bucket, you need to install the `s3fs` package:

    pipx inject f2-commander s3fs

"Connect" dialog is in its "alpha" version, exposing the underlying connector
configuration in a very generic way. Refer to the documentation of the installed
additional packages for more information.

### Remote bookmarks

It is possible to persist a connection for a remote file system, to quickly
reconnect to it without using the connection dialog. See the "Remote file systems"
section in the "Configuration" below.

## Archives

F2 Comamnder can read and extract archives and compressed files supported by
`libarchive`. A non-exhaustive list includes: ZIP, TAR, XAR, LHA/LZH, ISO 0660
(optical disc files), cpio, mtree, shar, ar, pax, RAR, MS CAB, 7-Zip, WARC, and more.
See https://github.com/libarchive/libarchive for more information.

To view and extract files from from an archive, open it (`Enter ⮐`) and copy the files
from it.

### Creating an archive

To create an archive, select one or multiple files and directories, and run the
"Create an archive" action from the Command Palette (`Ctrl+p`).

Target file extension determines an archival and a compression format. Following
extensions are recognized: `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tbz2`,
`.tar.xz`, `.txz`, `.7z`, `.ar`, `.cpio`, `.warc`.

## File preview

F2 Commander can preview text files and images.

To open a file preview panel, use `Ctrl+e` or `Ctrl+r` to switch to the "Preview"
panel on the left or on the right, and navigate to the file to preview in the other
panel.

For text files, only a head of the file is displayed, and the syntax is highlighted
if the file type is recognized. Use `v`/`F3` (view) action to view the file in the
default viewer program (`$VIEWER`) in full.

Image preview only works in terminal emulators that support TGP or Sixel.

## Panel types

F2 Commander comes with these panel types:

 - Files: default panel type, for file system discovery and manipulation
 - Preview: preview text and image files selected in the other Files panel
 - Help: also invoked with `?`/`F1` binding, a user manual (this one)

Use `Ctrl+e` and `Ctrl+r` to change the type of the panel on the left and right
respectively.

## Configuration

 - `Ctrl+,` opens the configuration dialog
 - Alternatively, find "Configuration" action in the Command Palette (`Ctrl+p`)

### Key mapping

F2 Commander comes with two predefined key mappings:

 - a traditional Function-key mapping: `F5` to copy file, `F6` to move, etc.,
 which is well known in orthodox file managers
 - and a Vi-like mnemonics-based mapping: `c` to copy, `m` to move, etc.

The latter is designed to for modern laptop keyboards, provided that you use
the top row keys as media keys (brightness, track control, etc.). It is enabled
by default. You can easily switch to the "Function keys" in the configuration,
if you prefer a traditional Fn-key experience.

### Themes (colors)

Several color themes are built-in and can be changed in the configuration dialog.

At the moment the colors are not customizable (you can only use the predefined themes).

### Configuration file

Unusually, you won't need to modify the configuration file directly. However, if
absolutely needed, your configuration file is:

    {str(user_config_path())}

Beware, the application may also write to the configuration file as you use it.

### Remote file systems

Connection configuration for remote file systems can be persisted and accessed
from the "Bookmarks" dialog.

Connection configuration is defined under `file_systems`, as a list of connection
objects. Each connection object defines:

 - `display_name`: a title that will be shown in the bookmarks list
 - `protocol`: a name of the protocol recognized by fsspec
 - `path`: an optional default path to navigate to upon connecting (defaults to root)
 - other keys are considered to be fsspec `storage_options`
   (see https://filesystem-spec.readthedocs.io/en/latest/api.html#fsspec.filesystem)

Refer to the documentation of the installed additional packages for more information
about the remote file system configuration.

For example, to connect to an ADLS Gen2 storage account:

    file_systems = [
      {{
        "display_name": "My BLOB storage",
        "protocol": "abfs",
        "params": {{
          "account_name": "myaccount",
          "account_key": "mykey"
        }}
      }}
    ]

To connect to a remote file system you may need to install additional packages that
provide `fsspec` implementations for the desired protocol. To find the name of the
package, if it is missing, use the "Connect" dialog (`Ctrl+t`).

For example, if you installed F2 Commander with `pipx`, and you want to connect
to an S3 bucket, you need to install the `s3fs` package:

    pipx inject f2-commander s3fs

## License

This application is provided "as is", without warranty of any kind.
This application is licensed under the Mozilla Public License, v. 2.0.
You can find a copy of the license at https://mozilla.org/MPL/2.0/
"""  # noqa: E501


class Help(Static):
    BINDINGS = [
        Binding("t", "toggle_toc", show=False),
        Binding("escape", "close", show=False),
        Binding("backspace", "close", show=False),
        Binding("q", "close", show=False),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewer = None

    def compose(self) -> ComposeResult:
        parent: Widget = self.parent  # type: ignore
        parent.border_title = "Help"
        parent.border_subtitle = None
        self.viewer = MarkdownViewer(HELP, show_table_of_contents=False)
        yield self.viewer

    def on_mount(self, event):
        # switch focus to the Help panel:
        self.app.screen.focus_next()

    def action_toggle_toc(self):
        self.viewer.show_table_of_contents = not self.viewer.show_table_of_contents

    def action_close(self):
        self.parent.panel_type = "file_list"  # type: ignore
        self.app.focus_next_panel()

    def on_key(self, event):
        if event.key == "j":
            self.viewer.scroll_down()
        elif event.key == "k":
            self.viewer.scroll_up()
