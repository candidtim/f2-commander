from textual.app import App, ComposeResult
from textual.widgets import Footer, Static


class TextualCommander(App):
    CSS_PATH = "tcss/main.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Textual Commander", id="title")
        yield Footer()


def main():
    app = TextualCommander()
    app.run()


if __name__ == "__main__":
    main()
