# view/app.py
# Main game loop for StartUps.
# Run with:  python -m view.app   (from the project root)

from __future__ import annotations

import os
from enum import Enum, auto

import readchar
from rich.console import Console

from model.loader import load_game_box
from model.save_load import default_save_name, list_saves, load_game, save_game
from model.state import GamePhase, new_game
from view.renderer import (
    LobbySlot,
    ViewState,
    MIN_PLAYERS,
    MAX_PLAYERS,
    _CONFIRM_OPTIONS,
    _OVER_OPTIONS,
    _SESSION_OPTIONS,
    available_actions,
    render_load_screen,
    render_lobby,
    render_new_game_confirm,
    render_save_screen,
    render_screen,
)


# ── Top-level entry point ─────────────────────────────────────────

def run() -> None:
    """Launch the lobby, then loop: lobby → game → lobby (or quit)."""
    console = Console()
    box     = load_game_box()

    while True:
        lobby_slots = _run_lobby(console)
        if lobby_slots is None:          # player pressed Q in lobby
            _goodbye(console)
            return

        outcome = _run_game(console, box, lobby_slots)
        if outcome == "quit":
            _goodbye(console)
            return
        # "new_game" and "play_again" both go back to the lobby


# ── Lobby ─────────────────────────────────────────────────────────

def _run_lobby(console: Console) -> list[LobbySlot] | None:
    """Show the player-setup screen.

    Returns a non-empty list of LobbySlot when the player confirms, or
    None when they press Q to quit the application.
    """
    slots         = [LobbySlot("Alice"), LobbySlot("Bob"), LobbySlot("Charlie")]
    cursor        = 0           # row index (0..len(slots) = Start Game)
    editing_index: int | None = None
    edit_buf:      list[str]  = []

    while True:
        render_lobby(console, slots, cursor, editing_index, edit_buf)
        key = readchar.readkey()

        # ── Name-editing sub-mode ──────────────────────────────────
        if editing_index is not None:
            if key in (readchar.key.ENTER, "\r", "\n"):
                name = "".join(edit_buf).strip()
                if name:
                    slots[editing_index].name = name
                editing_index = None
                edit_buf      = []

            elif key == readchar.key.ESCAPE:
                editing_index = None
                edit_buf      = []

            elif key in (readchar.key.BACKSPACE, "\x08", "\x7f"):
                if edit_buf:
                    edit_buf.pop()

            elif key.isprintable():
                edit_buf.append(key)

            continue

        # ── Normal navigation ──────────────────────────────────────
        total_rows = len(slots) + 1   # player rows + Start Game

        if key == readchar.key.UP:
            cursor = (cursor - 1) % total_rows

        elif key == readchar.key.DOWN:
            cursor = (cursor + 1) % total_rows

        elif key in (readchar.key.LEFT, readchar.key.RIGHT):
            if cursor < len(slots):
                slots[cursor].is_ai = not slots[cursor].is_ai

        elif key in (readchar.key.ENTER, "\r", "\n"):
            if cursor == len(slots):        # Start Game
                if len(slots) >= MIN_PLAYERS:
                    return slots
            else:                           # edit player name
                editing_index = cursor
                edit_buf      = list(slots[cursor].name)

        elif key in ("a", "A"):
            if len(slots) < MAX_PLAYERS:
                new_index = len(slots)
                slots.append(LobbySlot(f"Player {new_index + 1}"))
                cursor = new_index          # jump to new row

        elif key in ("r", "R"):
            if len(slots) > MIN_PLAYERS:
                slots.pop(cursor)
                cursor = min(cursor, len(slots))   # clamp; may land on Start Game

        elif key in ("q", "Q"):
            return None


# ── Game ──────────────────────────────────────────────────────────

class _GameMode(Enum):
    PLAYING          = auto()
    NEW_GAME_CONFIRM = auto()
    SAVE_INPUT       = auto()
    LOAD_PICKER      = auto()


def _run_game(
    console:     Console,
    box,
    lobby_slots: list[LobbySlot],
) -> str:
    """Run one full game session.

    Returns:
        "quit"       — user wants to exit the application
        "new_game"   — user chose New Game (go back to lobby)
        "play_again" — user chose Play Again after game over (go back to lobby)
    """
    from controller.session import GameSession
    from controller.slots import AgentSlot, HumanSlot
    from controller.agents.random_agent import RandomAgent

    player_names = [ls.name  for ls in lobby_slots]
    ai_set       = {ls.name  for ls in lobby_slots if ls.is_ai}

    # state_ref is a one-element list so HumanSlots always see the current state
    # even after load-game / new-game replaces the state object.
    state     = new_game(box, player_names)
    state_ref = [state]

    def make_slots() -> list:
        return [
            AgentSlot(name, RandomAgent()) if name in ai_set
            else HumanSlot(name, state_ref)
            for name in player_names
        ]

    def make_session() -> GameSession:
        return GameSession(state_ref[0], make_slots())

    session = make_session()
    view    = ViewState()

    mode: _GameMode    = _GameMode.PLAYING
    confirm_cursor     = 1          # default to "No" (safer)
    save_buf: list[str] = []
    load_saves_list     = []
    load_cursor         = 0

    while True:
        state = state_ref[0]        # always read through the ref

        actions = (
            available_actions(state)
            if state.game_phase != GamePhase.GAME_OVER
            else []
        )

        # ── NEW GAME CONFIRM ──────────────────────────────────────
        if mode == _GameMode.NEW_GAME_CONFIRM:
            render_new_game_confirm(console, confirm_cursor)
            key = readchar.readkey()

            if key == readchar.key.UP:
                confirm_cursor = (confirm_cursor - 1) % len(_CONFIRM_OPTIONS)
            elif key == readchar.key.DOWN:
                confirm_cursor = (confirm_cursor + 1) % len(_CONFIRM_OPTIONS)
            elif key in (readchar.key.ENTER, "\r", "\n"):
                if confirm_cursor == 0:     # Yes
                    return "new_game"
                mode = _GameMode.PLAYING
            elif key in (readchar.key.ESCAPE, "q", "Q"):
                mode = _GameMode.PLAYING
            continue

        # ── SAVE INPUT ────────────────────────────────────────────
        if mode == _GameMode.SAVE_INPUT:
            render_save_screen(console, save_buf)
            key = readchar.readkey()

            if key in (readchar.key.ENTER, "\r", "\n"):
                name = "".join(save_buf).strip() or default_save_name()
                save_game(state, name)
                mode = _GameMode.PLAYING
            elif key == readchar.key.ESCAPE:
                mode = _GameMode.PLAYING
            elif key in (readchar.key.BACKSPACE, "\x08", "\x7f"):
                if save_buf:
                    save_buf.pop()
            elif key.isprintable():
                save_buf.append(key)
            continue

        # ── LOAD PICKER ───────────────────────────────────────────
        if mode == _GameMode.LOAD_PICKER:
            render_load_screen(console, load_saves_list, load_cursor)
            key = readchar.readkey()

            if key == readchar.key.UP:
                load_cursor = max(0, load_cursor - 1)
            elif key == readchar.key.DOWN:
                load_cursor = min(len(load_saves_list) - 1, load_cursor + 1)
            elif key in (readchar.key.ENTER, "\r", "\n"):
                if load_saves_list:
                    state_ref[0] = load_game(load_saves_list[load_cursor], box)
                    session      = make_session()
                    view         = ViewState()
                mode = _GameMode.PLAYING
            elif key in (readchar.key.ESCAPE, "q", "Q"):
                mode = _GameMode.PLAYING
            continue

        # ── GAME OVER ─────────────────────────────────────────────
        if state.game_phase == GamePhase.GAME_OVER:
            render_screen(console, state, view, actions)
            key = readchar.readkey()

            if key == readchar.key.UP:
                view.menu_cursor = (view.menu_cursor - 1) % len(_OVER_OPTIONS)
            elif key == readchar.key.DOWN:
                view.menu_cursor = (view.menu_cursor + 1) % len(_OVER_OPTIONS)
            elif key in (readchar.key.ENTER, "\r", "\n"):
                if view.menu_cursor == 0:       # Play Again
                    return "play_again"
                else:                           # Quit
                    return "quit"
            elif key in ("q", "Q"):
                return "quit"
            continue

        # ── AI turn: advance automatically ────────────────────────
        current_slot = session.slots[state.current_player_index]
        from controller.slots import HumanSlot as _HumanSlot
        if not isinstance(current_slot, _HumanSlot):
            session.step()
            continue

        # ── PLAYING (human turn) ──────────────────────────────────
        render_screen(console, state, view, actions)
        key = readchar.readkey()

        if key == readchar.key.LEFT:
            view.navigate(-1, len(state.players))

        elif key == readchar.key.RIGHT:
            view.navigate(1, len(state.players))

        elif key == readchar.key.UP:
            if view.panel_index == 0:
                view.move_session_cursor(-1)
            elif view.panel_index == 1:
                view.scroll_history(-1, len(state.history))
            else:
                view.move_cursor(-1, len(actions))

        elif key == readchar.key.DOWN:
            if view.panel_index == 0:
                view.move_session_cursor(1)
            elif view.panel_index == 1:
                view.scroll_history(1, len(state.history))
            else:
                view.move_cursor(1, len(actions))

        elif key in (readchar.key.ENTER, "\r", "\n"):
            if view.panel_index == 0:
                opt = _SESSION_OPTIONS[view.session_cursor]
                if opt == "New Game":
                    confirm_cursor = 1
                    mode = _GameMode.NEW_GAME_CONFIRM
                elif opt == "Save Game":
                    save_buf = list(default_save_name())
                    mode = _GameMode.SAVE_INPUT
                elif opt == "Load Game":
                    load_saves_list = list_saves()
                    load_cursor     = 0
                    mode = _GameMode.LOAD_PICKER
                elif opt == "Quit":
                    return "quit"
            else:
                if view.panel_index - 3 == state.current_player_index and actions:
                    cursor = min(view.menu_cursor, len(actions) - 1)
                    actions[cursor].execute()
                    view.reset_action_cursor()

        elif key in ("q", "Q"):
            return "quit"


# ── Helpers ───────────────────────────────────────────────────────

def _goodbye(console: Console) -> None:
    os.system("clear")
    console.print("\n  [bold magenta]Thanks for playing StartUps![/bold magenta]\n")


if __name__ == "__main__":
    run()
