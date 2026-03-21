# view/app.py
# Main game loop for StartUps.
# Run with:  python -m view.app   (from the project root)

from __future__ import annotations

import os
import sys
from enum import Enum, auto

import readchar
from rich.console import Console

from model.loader import load_game_box
from model.save_load import default_save_name, list_saves, load_game, save_game
from model.state import GamePhase, new_game
from view.renderer import (
    ViewState,
    _CONFIRM_OPTIONS,
    _OVER_OPTIONS,
    _SESSION_OPTIONS,
    available_actions,
    render_load_screen,
    render_new_game_confirm,
    render_save_screen,
    render_screen,
)


class AppMode(Enum):
    PLAYING          = auto()
    NEW_GAME_CONFIRM = auto()   # confirm before wiping current session
    SAVE_INPUT       = auto()   # player is typing a save-file name
    LOAD_PICKER      = auto()   # player is picking a save file to load


def run(player_names: list[str] | None = None) -> None:
    box = load_game_box()
    if player_names is None:
        player_names = ["Alice", "Bob", "Charlie"]

    state   = new_game(box, player_names)
    view    = ViewState()
    console = Console()

    mode: AppMode  = AppMode.PLAYING
    confirm_cursor: int = 0             # cursor in the new-game confirm menu
    save_buf: list[str] = []            # character buffer for save-name input
    load_saves_list     = []            # save files shown in the load picker
    load_cursor: int    = 0

    while True:
        actions = (
            available_actions(state)
            if state.game_phase != GamePhase.GAME_OVER
            else []
        )

        # ── NEW GAME CONFIRM mode ─────────────────────────────────
        if mode == AppMode.NEW_GAME_CONFIRM:
            render_new_game_confirm(console, confirm_cursor)
            key = readchar.readkey()

            if key == readchar.key.UP:
                confirm_cursor = (confirm_cursor - 1) % len(_CONFIRM_OPTIONS)
            elif key == readchar.key.DOWN:
                confirm_cursor = (confirm_cursor + 1) % len(_CONFIRM_OPTIONS)
            elif key in (readchar.key.ENTER, "\r", "\n"):
                if confirm_cursor == 0:     # Yes
                    state = new_game(box, player_names)
                    view  = ViewState()
                mode = AppMode.PLAYING
            elif key in (readchar.key.ESCAPE, "q", "Q"):
                mode = AppMode.PLAYING

            continue

        # ── SAVE INPUT mode ───────────────────────────────────────
        if mode == AppMode.SAVE_INPUT:
            render_save_screen(console, save_buf)
            key = readchar.readkey()

            if key in (readchar.key.ENTER, "\r", "\n"):
                name = "".join(save_buf).strip() or default_save_name()
                save_game(state, name)
                mode = AppMode.PLAYING

            elif key == readchar.key.ESCAPE:
                mode = AppMode.PLAYING

            elif key in (readchar.key.BACKSPACE, "\x08", "\x7f"):
                if save_buf:
                    save_buf.pop()

            elif key.isprintable():
                save_buf.append(key)

            continue

        # ── LOAD PICKER mode ──────────────────────────────────────
        if mode == AppMode.LOAD_PICKER:
            render_load_screen(console, load_saves_list, load_cursor)
            key = readchar.readkey()

            if key == readchar.key.UP:
                load_cursor = max(0, load_cursor - 1)

            elif key == readchar.key.DOWN:
                load_cursor = min(len(load_saves_list) - 1, load_cursor + 1)

            elif key in (readchar.key.ENTER, "\r", "\n"):
                if load_saves_list:
                    state = load_game(load_saves_list[load_cursor], box)
                    view  = ViewState()
                mode = AppMode.PLAYING

            elif key in (readchar.key.ESCAPE, "q", "Q"):
                mode = AppMode.PLAYING

            continue

        # ── GAME OVER screen ──────────────────────────────────────
        if state.game_phase == GamePhase.GAME_OVER:
            render_screen(console, state, view, actions)
            key = readchar.readkey()

            if key == readchar.key.UP:
                view.menu_cursor = (view.menu_cursor - 1) % len(_OVER_OPTIONS)
            elif key == readchar.key.DOWN:
                view.menu_cursor = (view.menu_cursor + 1) % len(_OVER_OPTIONS)
            elif key in (readchar.key.ENTER, "\r", "\n"):
                if view.menu_cursor == 0:       # Play Again
                    state = new_game(box, player_names)
                    view  = ViewState()
                else:                           # Quit
                    _goodbye(console)
                    return
            elif key in ("q", "Q"):
                _goodbye(console)
                return
            continue

        # ── PLAYING mode ──────────────────────────────────────────
        render_screen(console, state, view, actions)
        key = readchar.readkey()

        if key == readchar.key.LEFT:
            view.navigate(-1, len(state.players))

        elif key == readchar.key.RIGHT:
            view.navigate(1, len(state.players))

        elif key == readchar.key.UP:
            if view.panel_index == 0:
                view.move_session_cursor(-1)
            else:
                view.move_cursor(-1, len(actions))

        elif key == readchar.key.DOWN:
            if view.panel_index == 0:
                view.move_session_cursor(1)
            else:
                view.move_cursor(1, len(actions))

        elif key in (readchar.key.ENTER, "\r", "\n"):
            if view.panel_index == 0:
                opt = _SESSION_OPTIONS[view.session_cursor]
                if opt == "New Game":
                    confirm_cursor = 1      # default to "No" (safer)
                    mode = AppMode.NEW_GAME_CONFIRM
                elif opt == "Save Game":
                    save_buf = list(default_save_name())
                    mode = AppMode.SAVE_INPUT
                elif opt == "Load Game":
                    load_saves_list = list_saves()
                    load_cursor = 0
                    mode = AppMode.LOAD_PICKER
                elif opt == "Quit":
                    _goodbye(console)
                    return
            else:
                # Execute game action only on the current player's own panel
                if view.panel_index - 2 == state.current_player_index and actions:
                    cursor = min(view.menu_cursor, len(actions) - 1)
                    actions[cursor].execute()
                    view.reset_action_cursor()

        elif key in ("q", "Q"):
            _goodbye(console)
            return


def _goodbye(console: Console) -> None:
    os.system("clear")
    console.print("\n  [bold magenta]Thanks for playing StartUps![/bold magenta]\n")


if __name__ == "__main__":
    run()
