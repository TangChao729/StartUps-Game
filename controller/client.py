# controller/client.py
# StartUps TCP game client.
#
# Clone the repo on your machine, then run:
#   python -m controller.client --host <server_ip> [--port 55001]
#
# The server assigns your player name when you connect.
# You'll see the same rich terminal UI as a local game.
# While waiting for other players, the History panel is shown automatically.

from __future__ import annotations

import json
import os
import socket
import sys
import termios
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import readchar
from rich.console import Console

from model.loader import load_game_box, GameBox
from model.pieces import Card, Coin
from model.state import (
    CompanyResult,
    GamePhase,
    GameResult,
    GameState,
    Market,
    MarketSlot,
    Player,
    TurnPhase,
)
from view.renderer import Action, ViewState, render_screen

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 55_001


# ── State reconstruction ──────────────────────────────────────────

def _restore_state(snapshot: dict, box: GameBox) -> tuple[GameState, list[Action]]:
    """Reconstruct a display-only GameState from a server snapshot.

    The viewing player's hand contains real Card objects.
    All other players' hands are filled with dummy Card objects so that
    len(player.hand) is correct for the 'X cards (hidden)' display.
    """
    company_map   = {c.id: c for c in box.companies}
    dummy_company = box.companies[0]

    def make_card(d: dict) -> Card:
        return Card(company=company_map[d["company_id"]], number=d["number"])

    def make_coins(denoms: list[int]) -> list[Coin]:
        return [Coin(d) for d in denoms]

    viewer_index = snapshot["player_index"]
    players: list[Player] = []
    for i, p in enumerate(snapshot["players"]):
        if i == viewer_index:
            hand = [make_card(c) for c in p["hand"]]
        else:
            # Dummy cards preserve hand count; names/colors are never shown
            # because is_current is False for non-active players → 'hidden'
            hand = [Card(company=dummy_company, number=0)
                    for _ in range(p["hand_size"])]
        players.append(Player(
            name    = p["name"],
            coins   = make_coins(p["coins"]),
            hand    = hand,
            tableau = [make_card(c) for c in p["tableau"]],
        ))

    player_map = {p.name: p for p in players}

    am_tokens = {
        cid: (player_map.get(name) if name else None)
        for cid, name in snapshot["am_tokens"].items()
    }

    market = Market(slots=[
        MarketSlot(
            card  = make_card({"company_id": s["company_id"],
                               "number":     s["number"]}),
            coins = make_coins(s["coins"]),
        )
        for s in snapshot["market_slots"]
    ])

    # Deck is face-down; only its size matters for rendering
    deck = [Card(company=dummy_company, number=0)] * snapshot["deck_size"]

    # Reconstruct GameResult for the game-over screen
    result = None
    if snapshot.get("result"):
        r   = snapshot["result"]
        crs = [
            CompanyResult(
                company_name = cr["company_name"],
                leader       = player_map.get(cr["leader"]) if cr.get("leader") else None,
                card_counts  = cr["card_counts"],
            )
            for cr in r["company_results"]
        ]
        result = GameResult(
            company_results = crs,
            final_standings = [tuple(pair) for pair in r["final_standings"]],
        )

    state = GameState(
        players       = players,
        deck          = deck,
        market        = market,
        companies     = box.companies,
        meta          = box.meta,
        am_tokens     = am_tokens,
        current_player_index       = snapshot["current_player_index"],
        phase                      = TurnPhase[snapshot["phase"]],
        game_phase                 = GamePhase[snapshot["game_phase"]],
        last_market_buy_company_id = snapshot.get("last_market_buy_company_id"),
        history                    = snapshot["history"],
        result                     = result,
    )

    # Actions are labels only; execute is a no-op (client sends index to server)
    actions = [
        Action(label=lbl, execute=lambda: None)
        for lbl in snapshot.get("actions", [])
    ]

    return state, actions


# ── Main client loop ──────────────────────────────────────────────

def run_client(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    console = Console()
    box     = load_game_box()

    console.print(f"\n  Connecting to [bold]{host}:{port}[/bold] ...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    rfile = sock.makefile("r", encoding="utf-8")
    console.print("  Connected!\n")

    def send(msg: dict) -> None:
        sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))

    def recv() -> dict:
        line = rfile.readline()
        if not line:
            raise ConnectionError("Server closed the connection.")
        return json.loads(line.strip())

    # ── Welcome ───────────────────────────────────────────────────
    welcome   = recv()
    my_name   = welcome["player_name"]
    all_names = welcome["all_players"]
    my_index  = all_names.index(my_name)

    console.print(
        f"  You are [bold green]{my_name}[/bold green] "
        f"(player {my_index + 1} of {len(all_names)}).\n"
        f"  Waiting for game to start...\n"
    )

    # Start on the viewing player's own panel
    view = ViewState(panel_index=3 + my_index)

    # ── Main loop ─────────────────────────────────────────────────
    try:
        while True:
            msg = recv()

            # ── Game over (dedicated message) ─────────────────────
            if msg["type"] == "game_over":
                state, _ = _restore_state(msg["snapshot"], box)
                _show_game_over(console, state, view)
                break

            if msg["type"] != "state":
                continue

            snapshot       = msg["snapshot"]
            state, actions = _restore_state(snapshot, box)

            # Game over can also arrive via a state message
            if state.game_phase == GamePhase.GAME_OVER:
                _show_game_over(console, state, view)
                break

            # ── MY TURN ───────────────────────────────────────────
            if snapshot["current_player_index"] == my_index:
                view.panel_index = 3 + my_index     # snap to own panel
                _handle_my_turn(console, state, view, actions, my_index, send)

            # ── NOT MY TURN ───────────────────────────────────────
            else:
                current_name = state.players[snapshot["current_player_index"]].name
                view.panel_index = 1                # history panel while waiting
                render_screen(console, state, view, [])
                console.print(
                    f"\n  [dim]Waiting for [bold]{current_name}[/bold]"
                    f" to play...[/dim]"
                )

    except ConnectionError as exc:
        console.print(f"\n  [bold red]Connection lost: {exc}[/bold red]")
    finally:
        sock.close()


def _drain_stdin() -> None:
    """Flush any buffered keyboard input (e.g. the \\n left after \\r from Enter).

    Prevents a stale keypress from firing an unintended action in the next
    readchar.readkey() call.  Silently ignored on platforms without termios.
    """
    try:
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass


def _handle_my_turn(
    console:  Console,
    state:    GameState,
    view:     ViewState,
    actions:  list[Action],
    my_index: int,
    send,
) -> None:
    """Render the board and block on keyboard until the player confirms an action."""
    while True:
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
            # Only confirm on the player's own panel
            if view.panel_index - 3 == my_index and actions:
                cursor = min(view.menu_cursor, len(actions) - 1)
                send({"type": "action", "index": cursor})
                view.reset_action_cursor()
                _drain_stdin()          # discard any buffered keypresses
                os.system("clear")
                console.print("\n  [dim]Action sent — waiting for server...[/dim]")
                return   # wait for next state from server

        elif key in ("q", "Q"):
            os.system("clear")
            raise ConnectionError("Player quit.")


def _show_game_over(console: Console, state: GameState, view: ViewState) -> None:
    render_screen(console, state, view, [])
    console.print(
        "\n  [bold magenta]Game over!  "
        "Press any key to exit.[/bold magenta]"
    )
    readchar.readkey()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="StartUps TCP game client")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"Server IP address (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"TCP port (default: {DEFAULT_PORT})")
    args = parser.parse_args()
    run_client(args.host, args.port)
