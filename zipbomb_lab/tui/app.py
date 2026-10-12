# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""The Textual application: a full-screen, keyboard-first lab console.

The app owns shared services (archive, settings) and the command registry, and
renders structured events published by the service. It never contains archive
logic itself — screens call the services and display the results.
"""

from __future__ import annotations

import threading
from pathlib import Path

from textual.app import App
from textual.events import Resize
from textual.reactive import reactive

from ..commands import build_registry
from .. import credits as _z
from ..infrastructure.terminal import detect_caps
from ..services import ArchiveService, SettingsService
from ..services.events import (
    ArchiveCompletedEvent,
    ArchiveFailedEvent,
    ArchiveProgressEvent,
    ArchiveStartedEvent,
    ArchiveWarningEvent,
    EventBus,
)
from ..ui import active_theme_name
from .keys import GLOBAL_BINDINGS
from .provider import LabCommandsProvider
from .state import AppState

__all__ = ["LabApp", "run_tui", "NARROW_WIDTH"]

#: Below this many columns the app drops side panels and tightens padding.
NARROW_WIDTH = 90


class LabApp(App):
    """The interactive console."""

    CSS_PATH = "styles/app.tcss"
    TITLE = "Zip Bomb Lab"
    BINDINGS = GLOBAL_BINDINGS
    COMMANDS = {LabCommandsProvider}
    COMMAND_PALETTE_BINDING = "ctrl+k"
    ENABLE_COMMAND_PALETTE = True

    def __init__(
        self,
        *,
        settings: SettingsService | None = None,
        service: ArchiveService | None = None,
        config=None,
        config_path: Path | None = None,
        bus: EventBus | None = None,
    ) -> None:
        super().__init__()
        self.state = AppState()
        self.settings = settings or SettingsService(config_path)
        self.config = config
        self.service = service or ArchiveService(bus)
        self.registry = build_registry()
        self._events: list = []
        self._lock = threading.RLock()
        self.service.bus.subscribe(self._on_event)

    # -- lifecycle ---------------------------------------------------------
    def on_mount(self) -> None:
        _z.n()
        from .screens.home import HomeScreen

        if self.config is None:
            self.config, warnings = self.settings.load()
            for warning in warnings:
                self.log.warning(warning)
        try:
            self.settings.apply_theme(self.config)
        except Exception:  # pragma: no cover - theme is cosmetic
            pass
        self.push_screen(HomeScreen())
        self.set_interval(0.1, self._drain_events)

    def on_resize(self, event: Resize) -> None:
        narrow = event.size.width < NARROW_WIDTH
        for screen in self.screen_stack:
            screen.set_class(narrow, "-narrow")

    # -- event plumbing ----------------------------------------------------
    def _on_event(self, event) -> None:
        with self._lock:
            self._events.append(event)

    def _drain_events(self) -> None:
        with self._lock:
            pending, self._events = self._events, []
        if not pending:
            return
        for event in pending:
            if isinstance(event, ArchiveStartedEvent):
                if not self.state.operation.running:
                    self.state.begin("archive", event.job_label or "archive", event.total_bytes)
                else:
                    self.state.operation.total = int(event.total_bytes or 0)
            elif isinstance(event, ArchiveProgressEvent):
                self.state.advance(event.written, event.total)
            elif isinstance(event, ArchiveWarningEvent):
                self.state.warn(event.message)
            elif isinstance(event, (ArchiveCompletedEvent, ArchiveFailedEvent)):
                pass
        self._notify_progress()

    def _notify_progress(self) -> None:
        screen = self.screen
        tick = getattr(screen, "progress_tick", None)
        if callable(tick):
            try:
                tick()
            except Exception:  # pragma: no cover - a screen mid-teardown
                pass
        self.refresh_chrome()

    # -- chrome ------------------------------------------------------------
    def refresh_chrome(self) -> None:
        refresh = getattr(self.screen, "refresh_chrome", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:  # pragma: no cover
                pass

    def status_segments(self) -> list[tuple[str, str]]:
        nav = self.state.navigation
        op = self.state.operation
        if op.running:
            mode = f"{op.kind} {op.percent:4.1f}%"
        else:
            mode = "ready"
        return [
            ("DIR", nav.directory.name or str(nav.directory)),
            ("MODE", "interactive"),
            ("THEME", active_theme_name()),
            ("STATE", mode),
        ]

    # -- actions -----------------------------------------------------------
    def action_back(self) -> None:
        from .screens.home import HomeScreen

        if isinstance(self.screen, HomeScreen):
            self.state.navigation.note("already home")
            self.refresh_chrome()
            return
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_help(self) -> None:
        self.open_command("help")

    def action_quit_app(self) -> None:
        self.exit()

    def action_refresh(self) -> None:
        refresh = getattr(self.screen, "reload_view", None)
        if callable(refresh):
            refresh()
        self.refresh_chrome()

    def action_home_action(self, name: str) -> None:
        self.open_command(name)

    def go_home(self) -> None:
        from .screens.home import HomeScreen

        while not isinstance(self.screen, HomeScreen) and len(self.screen_stack) > 1:
            self.pop_screen()

    # -- navigation --------------------------------------------------------
    def open_command(self, name: str) -> None:
        """Route a command name (from the palette, a key or the home list)."""
        canonical = self.registry.canonical(name) or name
        if canonical in ("tui", "gui", "panel"):
            self.state.navigation.remember(canonical)
            self.go_home()
            return
        self.state.navigation.remember(canonical)

        factory = {
            "create": self._create_screen,
            "estimate": self._estimate_screen,
            "inspect": self._inspect_screen,
            "recipes": self._recipes_screen,
            "methods": self._methods_screen,
            "settings": self._settings_screen,
            "config": self._settings_screen,
            "help": self._help_screen,
            "policy": lambda: self._info_screen("policy"),
            "audit": lambda: self._info_screen("audit"),
            "version": lambda: self._info_screen("version"),
            "selftest": lambda: self._info_screen("selftest"),
            "about": lambda: self._about_screen(),
        }
        if canonical == "demo":
            self.push_screen(self._demo_screen())
            return
        maker = factory.get(canonical)
        if maker is None:
            suggestions = self.registry.suggestions(canonical)
            self._notify_error(
                f"Unknown command {canonical!r}",
                "That action is not registered.",
                hint=("Did you mean: " + ", ".join(suggestions)) if suggestions else "",
            )
            return
        self.push_screen(maker())

    # -- screen factories (lazy imports keep start-up snappy) --------------
    def _create_screen(self):
        from .screens.create import CreateScreen

        return CreateScreen()

    def _estimate_screen(self):
        from .screens.estimate import EstimateScreen

        return EstimateScreen()

    def _inspect_screen(self):
        from .screens.inspect import InspectScreen

        return InspectScreen()

    def _recipes_screen(self):
        from .screens.recipes import RecipesScreen

        return RecipesScreen()

    def _methods_screen(self):
        from .screens.methods import MethodsScreen

        return MethodsScreen()

    def _settings_screen(self):
        from .screens.settings import SettingsScreen

        return SettingsScreen()

    def _help_screen(self):
        from .screens.help import HelpScreen

        return HelpScreen()

    def _demo_screen(self):
        from .screens.demo import DemoScreen

        return DemoScreen()

    def _about_screen(self):
        from .screens.about import AboutScreen

        return AboutScreen()

    def _info_screen(self, which: str):
        from .screens.info import InfoScreen

        command = self.registry.get(which)
        body = ""
        if command is not None and command.handler is not None:
            from ..commands import CommandContext

            result = command.handler(CommandContext(service=self.service), [])
            body = result.message
        return InfoScreen(which.title(), body)

    # -- notifications -----------------------------------------------------
    def _notify_error(self, title: str, message: str, *, hint: str = "", details: str = "") -> None:
        from .dialogs import ErrorDialog

        self.state.navigation.note("error")
        self.push_screen(ErrorDialog(title, message, hint=hint, details=details))


def run_tui(
    *,
    config_path: Path | None = None,
    settings: SettingsService | None = None,
    service: ArchiveService | None = None,
) -> int:
    """Launch the interactive console (blocking; returns an exit code)."""
    app = LabApp(settings=settings, service=service, config_path=config_path)
    app.run()
    return 0


def can_use_tui() -> bool:
    """True when a full-screen console is safe to launch here."""
    return detect_caps().can_tui


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.app - made by Xv @XvRendering https://github.com/MamadXV"
