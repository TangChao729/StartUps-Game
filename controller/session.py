# controller/session.py
# GameSession: owns a GameState and a list of slots, drives the game loop.
#
# The session is the single authority on state mutation:
#   1. Ask the active slot for an action index.
#   2. Re-derive the live action list from state.
#   3. Execute the chosen action.
#   4. Repeat until GAME_OVER.

from __future__ import annotations

from model.state import GamePhase, GameState
from controller.serialiser import build_observation, build_result
from controller.slots import SlotBase
from view.renderer import available_actions


class GameSession:
    """Drives a single game to completion with a fixed list of player slots."""

    def __init__(self, state: GameState, slots: list[SlotBase]) -> None:
        if len(slots) != len(state.players):
            raise ValueError(
                f"Need exactly {len(state.players)} slots "
                f"(one per player), got {len(slots)}."
            )
        self.state = state
        self.slots = slots

    # ── Public API ────────────────────────────────────────────────

    def run(self) -> None:
        """Run the game to completion, then notify all slots."""
        while self.state.game_phase == GamePhase.PLAYING:
            self._step()
        self._notify_game_over()

    def step(self) -> bool:
        """Advance exactly one action.

        Returns True if the game is still in progress, False if it just ended.
        Useful for external loops that want to observe each transition.
        """
        if self.state.game_phase != GamePhase.PLAYING:
            return False
        self._step()
        if self.state.game_phase == GamePhase.GAME_OVER:
            self._notify_game_over()
            return False
        return True

    # ── Private ───────────────────────────────────────────────────

    def _step(self) -> None:
        idx    = self.state.current_player_index
        slot   = self.slots[idx]
        obs    = build_observation(self.state, idx)

        action_index = slot.request_action(obs)

        # Re-derive actions from live state (obs is a snapshot; closures are live)
        actions = available_actions(self.state)

        if not actions:
            raise RuntimeError("No legal actions available — game state is stuck.")
        if not (0 <= action_index < len(actions)):
            raise ValueError(
                f"Slot '{slot.player_name}' returned invalid action index "
                f"{action_index} (valid range: 0..{len(actions) - 1})."
            )

        actions[action_index].execute()

    def _notify_game_over(self) -> None:
        result = build_result(self.state)
        for slot in self.slots:
            slot.on_game_over(result)
