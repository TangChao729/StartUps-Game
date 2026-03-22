# controller/slots.py
# Player slot abstractions.  A slot is anything that can be asked to pick
# an action for a given player index.  The session doesn't care whether the
# slot is a local AI agent, a human at a keyboard, or a remote network client.

from __future__ import annotations

from abc import ABC, abstractmethod

from controller.agents.base import Agent


class SlotBase(ABC):
    """A seat at the table.  Corresponds 1-to-1 with a Player in GameState."""

    def __init__(self, player_name: str) -> None:
        self.player_name = player_name

    @abstractmethod
    def request_action(self, obs: dict) -> int:
        """Block until an action is chosen.

        Returns an index into obs['actions'].
        """

    def on_game_over(self, result: dict) -> None:
        """Called once when the game ends.  Override to react to results."""


class HumanSlot(SlotBase):
    """Slot backed by a human at a keyboard.  Uses the rich terminal UI.

    Takes a mutable state_ref (a one-element list) so it always sees the
    current GameState even after a load-game or new-game replaces it.
    """

    def __init__(self, player_name: str, state_ref: list) -> None:
        super().__init__(player_name)
        self._state_ref = state_ref

    @property
    def _state(self):
        return self._state_ref[0]

    def request_action(self, obs: dict) -> int:
        """Render the board and block on keyboard input until the player
        confirms an action.  Returns the chosen action index."""
        import readchar
        from rich.console import Console
        from view.renderer import ViewState, available_actions, render_screen

        console = Console()
        view    = ViewState(panel_index=3 + self._state.current_player_index)

        while True:
            actions = available_actions(self._state)
            render_screen(console, self._state, view, actions)
            key = readchar.readkey()

            if key == readchar.key.LEFT:
                view.navigate(-1, len(self._state.players))
            elif key == readchar.key.RIGHT:
                view.navigate(1, len(self._state.players))
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
                # Only confirm on the current player's own panel
                if (
                    view.panel_index - 3 == self._state.current_player_index
                    and actions
                ):
                    cursor = min(view.menu_cursor, len(actions) - 1)
                    view.reset_action_cursor()
                    return cursor


class AgentSlot(SlotBase):
    """Slot backed by a local Agent instance.  Never blocks."""

    def __init__(self, player_name: str, agent: Agent) -> None:
        super().__init__(player_name)
        self.agent = agent

    def request_action(self, obs: dict) -> int:
        return self.agent.choose_action(obs)

    def on_game_over(self, result: dict) -> None:
        self.agent.on_game_over(result)
