"""tests/test_session.py
Run 100 AI-only games using RandomAgent to verify the session loop
never crashes and always reaches GAME_OVER.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.loader import load_game_box
from model.state import GamePhase, new_game
from controller.session import GameSession
from controller.slots import AgentSlot
from controller.agents.random_agent import RandomAgent
from controller.serialiser import build_observation


def make_session(box, names):
    state = new_game(box, names)
    slots = [AgentSlot(n, RandomAgent()) for n in names]
    return GameSession(state, slots)


def test_observation_keys():
    """build_observation returns all expected keys."""
    box   = load_game_box()
    state = new_game(box, ["Alice", "Bob", "Charlie"])
    obs   = build_observation(state, 0)

    required = {
        "player_index", "player_name", "phase", "deck_size",
        "your_money", "your_hand", "your_tableau", "your_am_tokens",
        "market", "am_tokens", "opponents", "actions",
    }
    missing = required - obs.keys()
    assert not missing, f"Missing observation keys: {missing}"

    assert obs["player_index"] == 0
    assert obs["player_name"]  == "Alice"
    assert obs["phase"]        == "BUY"
    assert obs["deck_size"]    > 0
    assert len(obs["opponents"]) == 2
    assert len(obs["actions"])   > 0
    print("  observation keys: OK")


def test_random_agent_action_in_range():
    """RandomAgent always returns a valid action index."""
    box   = load_game_box()
    state = new_game(box, ["Alice", "Bob", "Charlie"])
    agent = RandomAgent()

    for _ in range(50):
        obs   = build_observation(state, state.current_player_index)
        idx   = agent.choose_action(obs)
        assert 0 <= idx < len(obs["actions"]), f"Bad index {idx}"
    print("  random agent index range: OK")


def test_full_game_completes():
    """A single AI-only game always reaches GAME_OVER."""
    box     = load_game_box()
    session = make_session(box, ["Alice", "Bob", "Charlie"])
    session.run()
    assert session.state.game_phase == GamePhase.GAME_OVER
    assert session.state.result is not None
    assert session.state.result.winner
    print(f"  single game winner: {session.state.result.winner} — OK")


def test_100_games():
    """Run 100 games, verify all complete without errors."""
    box    = load_game_box()
    names  = ["Alice", "Bob", "Charlie"]
    wins   = {}

    for i in range(100):
        session = make_session(box, names)
        session.run()
        assert session.state.game_phase == GamePhase.GAME_OVER, \
            f"Game {i} did not reach GAME_OVER"
        winner = session.state.result.winner
        wins[winner] = wins.get(winner, 0) + 1

    assert sum(wins.values()) == 100
    print(f"  100 games completed — win counts: {wins}")


def test_four_players():
    """Session works with 4 players."""
    box     = load_game_box()
    session = make_session(box, ["Alice", "Bob", "Charlie", "Dave"])
    session.run()
    assert session.state.game_phase == GamePhase.GAME_OVER
    print(f"  4-player winner: {session.state.result.winner} — OK")


if __name__ == "__main__":
    print("Running session tests...\n")
    box = load_game_box()

    test_observation_keys()
    test_random_agent_action_in_range()
    test_full_game_completes()
    test_100_games()
    test_four_players()

    print("\nAll tests passed.")
