# controller/agents/base.py
# Abstract base class for all agents (AI or otherwise).

from __future__ import annotations

from abc import ABC, abstractmethod


class Agent(ABC):
    """An agent that plays StartUps by choosing from pre-enumerated legal actions.

    On each turn the agent receives an observation dict (see serialiser.py)
    and returns an integer index into obs["actions"].  The caller is
    responsible for executing the chosen action — the agent only decides.
    """

    @abstractmethod
    def choose_action(self, obs: dict) -> int:
        """Return an index into obs['actions'].

        Must satisfy: 0 <= return_value < len(obs['actions'])
        """

    def on_game_over(self, result: dict) -> None:
        """Called once when the game ends.  Override to handle results."""
