# controller/agents/random_agent.py
# The simplest possible agent: picks a uniformly random legal action.

from __future__ import annotations

import random

from controller.agents.base import Agent


class RandomAgent(Agent):
    """Picks a uniformly random action from the legal action list."""

    def choose_action(self, obs: dict) -> int:
        return random.randrange(len(obs["actions"]))
