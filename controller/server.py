# controller/server.py
# StartUps TCP game server.
#
# One machine runs the server; remote players connect with controller/client.py.
# AI bots fill any slots not taken by human players.
#
# Usage:
#   python -m controller.server [--host HOST] [--port PORT]
#                               [--humans Alice Bob] [--ai Charlie]
#
# Clients must connect in the order listed in --humans (first connection = Alice,
# second = Bob, etc.).  The server prints progress as each client joins.

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from model.loader import load_game_box
from model.state import GamePhase, new_game
from controller.session import GameSession
from controller.slots import AgentSlot
from controller.agents.random_agent import RandomAgent
from controller.remote_slot import RemoteSlot
from controller.serialiser import build_result

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 55_001


def run_server(
    host:        str       = DEFAULT_HOST,
    port:        int       = DEFAULT_PORT,
    human_names: list[str] = None,   # names for remote human slots (connect in order)
    ai_names:    list[str] = None,   # names for RandomAgent bots
) -> None:
    """Start the game server and run one game to completion.

    Turn order is human_names first, then ai_names.
    """
    if human_names is None:
        human_names = ["Alice", "Bob"]
    if ai_names is None:
        ai_names = ["Charlie"]

    all_names = human_names + ai_names
    box       = load_game_box()

    print(f"[server] Binding {host}:{port}")
    print(f"[server] Human slots : {human_names}")
    print(f"[server] AI slots    : {ai_names}")
    print(f"[server] Turn order  : {all_names}")
    print(f"[server] Waiting for {len(human_names)} connection(s)...\n")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(len(human_names))

    # Accept one connection per human slot, in order
    connections: dict[str, socket.socket] = {}
    for name in human_names:
        print(f"[server] Waiting for '{name}'...")
        conn, addr = srv.accept()
        print(f"[server] '{name}' connected from {addr[0]}:{addr[1]}")
        connections[name] = conn
        welcome = json.dumps({
            "type":        "welcome",
            "player_name": name,
            "all_players": all_names,
        }) + "\n"
        conn.sendall(welcome.encode("utf-8"))

    srv.close()
    print(f"\n[server] All players connected — starting game!\n")

    # ── Build state and slots ──────────────────────────────────────
    state     = new_game(box, all_names)
    state_ref = [state]

    slots: list         = []
    remote_slots: list[RemoteSlot] = []

    for name in all_names:
        if name in human_names:
            idx    = all_names.index(name)
            remote = RemoteSlot(name, connections[name], idx, state_ref)
            slots.append(remote)
            remote_slots.append(remote)
        else:
            slots.append(AgentSlot(name, RandomAgent()))

    session = GameSession(state, slots)

    # Send initial state so every client can render before the first action
    for remote in remote_slots:
        remote.send_state(state)

    # ── Game loop ──────────────────────────────────────────────────
    try:
        while state.game_phase == GamePhase.PLAYING:
            session._step()

            if state.game_phase == GamePhase.GAME_OVER:
                break

            # Broadcast the updated state to every watching client.
            # The next-active remote client will receive their state via
            # request_action(); all others need an explicit push here.
            next_idx = state.current_player_index
            for remote in remote_slots:
                if remote.player_index != next_idx:
                    remote.send_state(state)

        # Notify every slot (sends game_over message to remote clients)
        session._notify_game_over()

    except ConnectionError as exc:
        print(f"\n[server] {exc}")
        print("[server] A player disconnected — game halted.")

    finally:
        for remote in remote_slots:
            remote.close()

    print("[server] Game finished.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="StartUps TCP game server")
    parser.add_argument("--host",   default=DEFAULT_HOST,
                        help=f"Interface to bind (default: {DEFAULT_HOST})")
    parser.add_argument("--port",   type=int, default=DEFAULT_PORT,
                        help=f"TCP port (default: {DEFAULT_PORT})")
    parser.add_argument("--humans", nargs="+", default=["Alice", "Bob"],
                        metavar="NAME",
                        help="Names for remote human players — clients must "
                             "connect in this order (default: Alice Bob)")
    parser.add_argument("--ai",     nargs="+", default=["Charlie"],
                        metavar="NAME",
                        help="Names for AI (RandomAgent) players "
                             "(default: Charlie)")
    args = parser.parse_args()
    run_server(args.host, args.port, args.humans, args.ai)
