# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Modal dialogs: confirmation and friendly, dismissible errors."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

__all__ = ["ConfirmDialog", "ErrorDialog"]


class ConfirmDialog(ModalScreen):
    """Ask a yes/no (or choose-one) question before a state change."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        detail: str = "",
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        third_label: str = "",
        danger: bool = False,
    ) -> None:
        super().__init__()
        self.title_text = title
        self.message = message
        self.detail = detail
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.third_label = third_label
        self.danger = danger

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal"):
            yield Static(self.title_text, classes="headline", id="confirm-title")
            yield Static(self.message, id="confirm-message")
            if self.detail:
                yield Static(self.detail, classes="detail", id="confirm-detail")
            with Horizontal(classes="buttons"):
                yield Button(
                    self.confirm_label,
                    variant="error" if self.danger else "primary",
                    id="confirm-yes",
                )
                if self.third_label:
                    yield Button(self.third_label, id="confirm-third")
                yield Button(self.cancel_label, id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss("confirm")
        elif event.button.id == "confirm-third":
            self.dismiss("third")
        else:
            self.dismiss(None)


class ErrorDialog(ModalScreen):
    """Present a failure as a problem with actions, not a stack trace."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        hint: str = "",
        details: str = "",
    ) -> None:
        super().__init__()
        self.title_text = title
        self.message = message
        self.hint = hint
        self.details = details
        self._showing = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal"):
            yield Static(self.title_text, classes="headline", id="error-title")
            yield Static(self.message, id="error-message")
            if self.hint:
                yield Static(self.hint, classes="detail")
            if self.details:
                yield Button("Show details", id="error-details")
                yield Static("", classes="detail", id="error-technical")
            with Horizontal(classes="buttons"):
                yield Button("Back", variant="primary", id="error-back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "error-details":
            self._showing = not self._showing
            target = self.query_one("#error-technical", Static)
            target.update(self.details if self._showing else "")
            event.button.label = "Hide details" if self._showing else "Show details"
        else:
            self.dismiss(None)


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.dialogs.modal - made by Xv @XvRendering https://github.com/MamadXV"
