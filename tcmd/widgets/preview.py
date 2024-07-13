from textual.app import ComposeResult
from textual.widgets import Static


class Preview(Static):
    def compose(self) -> ComposeResult:
        yield Static("HI")
