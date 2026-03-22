# controller/remote_slot.py
# A player slot backed by a remote client connected over TCP.
# Fits the SlotBase interface: request_action blocks on socket.recv()
# just like HumanSlot blocks on keyboard input.

from __future__ import annotations

import json
import socket

from controller.slots import SlotBase
from controller.serialiser import build_display_snapshot


class RemoteSlot(SlotBase):
    """Slot backed by a remote player connected over TCP.

    The server owns the socket.  request_action() sends the current game
    state snapshot to the client and blocks until it replies with an action
    index.  No threads required — the blocking is intentional.
    """

    def __init__(
        self,
        player_name:  str,
        conn:         socket.socket,
        player_index: int,
        state_ref:    list,        # one-element list [GameState] — always current
    ) -> None:
        super().__init__(player_name)
        self.player_index = player_index
        self._conn      = conn
        self._state_ref = state_ref
        self._rfile     = conn.makefile("r", encoding="utf-8")

    # ── Helpers ───────────────────────────────────────────────────

    def send(self, msg: dict) -> None:
        data = json.dumps(msg, ensure_ascii=False) + "\n"
        self._conn.sendall(data.encode("utf-8"))

    def send_state(self, state=None) -> None:
        """Push the current game state snapshot to this client."""
        if state is None:
            state = self._state_ref[0]
        snapshot = build_display_snapshot(state, self.player_index)
        self.send({"type": "state", "snapshot": snapshot})

    def close(self) -> None:
        try:
            self._conn.close()
        except OSError:
            pass

    # ── SlotBase interface ────────────────────────────────────────

    def request_action(self, obs: dict) -> int:
        """Send current state (it's this player's turn) then wait for reply."""
        self.send_state()
        while True:
            line = self._rfile.readline()
            if not line:
                raise ConnectionError(
                    f"Remote player '{self.player_name}' disconnected "
                    "while waiting for their action."
                )
            msg = json.loads(line.strip())
            if msg.get("type") == "action":
                return int(msg["index"])
            # ignore unknown message types (e.g. pings)

    def on_game_over(self, result: dict) -> None:
        """Send the final game state and result to this client."""
        state    = self._state_ref[0]
        snapshot = build_display_snapshot(state, self.player_index)
        self.send({"type": "game_over", "snapshot": snapshot, "result": result})
