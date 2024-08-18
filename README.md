# F2 Commander

F2 Commander is an orthodox file manager for the modern world.

![F2 Commander Demo](img/f2.png "F2 Commander")

## Status

F2 Commander is usable, with a core set of features implemented. While it is
functional, development is ongoing. See the "Roadmap" below for a complete
feature list and their status. This is a personal project with all its
implications. See the "About" section below for more information. Users are
encouraged to contribute and report issues.

## Installation

From source:

    poetry build
    pipx install [--force] dist/f2_commander-0.1.0.tar.gz

This software is designed to work in Linux and MacOS. It should also work in
WSL (Windows Subsystem for Linux).

## Usage

 - Start by running `f2` in your terminal emulator
 - Hit `?` to see the built-in help
 - Hit `q` to quit

## Roadmap

F2 Commander mission is to bring the experience of an orthodox file
manager into the world of modern computing.

F2 Commander main principles are:

 - "file system" can be anything that contains files, blobs, etc.
 - focus on the **tasks** for file manipulation
 - discoverability of file systems (making file systems easy to navigate)
 - discoverability of the tool itself (making it easy and evident to use)
 - the software should be easy to adapt, shape and extend

Features:

 - User Interface

   - [x] Two-panel interface
   - [x] Classic footer with common user actions
     - [ ] Contextual footer (changes actions based on context)
     - [ ] Configurable key bindings. "Modern" and "Retro" bindings out of the box.
   - [ ] Menubar
   - [x] Command Palette
   - [ ] File Info / Preview panel
   - [x] Drop to shell (command line) temporarily
   - [ ] Theming. "Modern" and "Retro" themes out of the box.

 - Configuration

   - [x] User configuration file
   - [ ] UI for most common configuration options
     - [ ] Options for user-defined viewer, editor, shell, and default file actions
     - [ ] Enable/disable CWD following the user selection
     - [ ] Enable/disable case sensitivity when ordering by name
     - [ ] List dirs first toggle
     - [ ] Starting directory for each pane (cwd, home, fixed path, or last location)

 - Navigation

   - [x] Basic file and directory info: entry names, human-readable size,
         last modification time, show and follow symlinks, etc.
   - [x] Vim-like (up/down j/k g/G ctrl+f/d/b/u) navigation
   - [x] Navigate "up" (with backspace or with the ".." entry)
   - [x] Order entries by name, size, time (last modification time)
   - [x] Filter entries with glob
   - [x] Directory summary in the file listing footer
   - [x] "List dirs first/inline" toggle
   - [x] Ordering by name case sensitivity on/off
   - [ ] Quick search: navigate file list by typing in the file names
   - [ ] Navigate to path (enter path, with auto-completion)
   - [ ] Bookmarks (set and navigate to the bookmarks)
   - [x] "Same location" and "Swap panels" actions
   - [ ] CWD follows user selection
   - [ ] Detect external changes and update file listing when possible
   - [x] Open current location in the OS default file manager

 - File and directory manipulation

   - [x] Basic operations like copy, move, move to trash, etc.
     - [x] Confirmation dialogs and user inputs (destination path, etc.)
     - [x] Multiple file selection
     - [ ] Progress bar for long operations
     - [ ] Option to delete files (as opposed to moving to trash)
   - [x] View and edit files using user default viewer and editor
   - [x] "Open" files with a default associated program (e.g., view PDF, etc.)
   - [ ] Run programs (run executable files)
   - [x] Create a new directory
   - [ ] Create a new file
   - [x] "Show/hide hidden files" toggle
   - [ ] Create and modify symlinks, show broken, and other symlink tasks
   - [ ] Compute directory size on selection

 - "File systems" support

   - [x] "Local" OS file system
   - [ ] AWS S3
   - [ ] GCP GCS
   - [ ] Dropbox
   - [ ] FTP, FTPS, SFTP
   - [ ] ... show must go on ...

 - Archival and compression support

   - [ ] ZIP (read, create, update)
   - [ ] ... and more ...

 - Documentation

   - [x] Built-in help
   - [ ] User manual

 - Windows support. You are probably better off with WSL, but some day, maybe...

   - [ ] Test all features in Windows
   - [ ] Then, maybe plan fixes

User experience and app behavior:

 - Dialogs

   - [ ] "Do not ask me again" option in "safe" dialogs (e.g., "Quit" dialog)
   - [ ] Allow "Enter" and "y" keys in "safe" dialogs for confirmation

 - Navigation

   - [x] Save user's choises between restarts (hidden files toggle, dirs first, etc.)
   - [ ] Consistent cursor positioning
     - [x] ... on the source directory when navigating "up"
     - [ ] ... on the source link when navigating back from symlink
     - [ ] ... on the nearest entry after delete or move
   - [ ] Clicking on list headers changes ordering in according columns

Known bugs to fix:

 - Restore the "show hidden files" state when switching back to the file list
   after having used a different panel type.

 - Errors in copy, move, etc. are not handled (e.g., destination directory
   doesn't exist, etc.). Note that not only preconditions should be checked,
   but also the errors should be handled (e.g., destination can be deleted
   during copy, network connection dropped, etc.)

 - ".." path is allowed for selection and can be copied, moved, etc.; handle
   ".." and empty selections better

 - File info and preview panels show nothing on start unless a selection is
   changed in the file list.

 - Default viewer, editor, shell and "open" programs are mostly MacOS-specific,
   choices are too rigid. Make sure defaults work on clean MacOS and Linux
   installs.

 - File list has an unnecessary 2-column (2 character wide) gap even when no
   vertical scroll bar is present (2 characters are reserved for the scroll
   bar)

 - Ctrl+U / Ctrl+D should scroll half a page (not en entire page)

 - Selection is always cleared if "Hidden files" toggle is changed

## Development environment

This project uses Poetry for dependency management and as a build tool. The
configuration is conventional, use as usual:

    poetry install --with dev

It also uses black, flake8, isort, mypy and pytest. An IDE or an LSP should
pick up their configuration, or they can be executed with poetry. For example:

    poetry run pytest

To run all code quality controls and linters:

    ./check

To run the application from source code:

    poetry run f2

To run the application with dev tools:

    poetry run textual console [-v -x SYSTEM -x EVENT -x DEBUG -x INFO]  # this first!
    poetry run textual run --dev f2.app:F2Commander

## About

"F2" is a loose interpretation of "a **F**ile manager with **2** side-by-side
panels", and "Commander" is an homage to the old-school orthodox file managers.

"F2 Commander" is a personal project that has grown into a full-fledged file
manager and is now open-sourced. Being a personal project means that: a) my
intent is to follow the "Roadmap" outlined above, but development and bug fixing
may be irregularly-paced and priorities may shift; b) the intent is to keep it
stable, yet future versions may include backward-incompatible changes where that
would seem practical to do.

## Contributions

Bug reports, feature requests and pull requests are welcome.

If you plan to contirbute to the source code, see the "Development environment"
above, and make sure to run the linters.

## License

This application is provided "as is", without warranty of any kind.

Mozilla Public License, v. 2.0.
