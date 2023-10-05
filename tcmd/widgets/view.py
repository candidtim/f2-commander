from pathlib import Path

from textual.app import ComposeResult
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header
from textual_terminal import Terminal


class MyTerminal(Terminal):
    class Stopped(Message):
        pass

    def stop(self):
        super().stop()
        self.post_message(self.Stopped())


class ViewScreen(Screen):
    BINDINGS = [("q", "app.pop_screen", "Quit")]

    DEFAULT_CSS = """
    #term {
        height: 1fr;
        border: $accent double;
    }
    """

    def __init__(self, src: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.src = src

    def compose(self) -> ComposeResult:
        yield Header()
        yield MyTerminal(command=f"view {str(self.src)}", id="term")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self.src.name
        terminal: Terminal = self.query_one("#term")
        terminal.start()

    def on_my_terminal_stopped(self, event: MyTerminal.Stopped):
        self.app.pop_screen()
