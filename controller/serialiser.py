# controller/serialiser.py
# Converts GameState into a plain dict observation for agents.
#
# Design principles:
#   - JSON-serialisable: no Python objects, only dicts/lists/str/int/bool/None
#   - Information hiding: opponents' hand contents are hidden (hand_size only)
#   - Actions are pre-enumerated: agent picks an index, never constructs a move
#   - Identical structure whether the agent runs locally or over a network

from __future__ import annotations

from model.pieces import Card
from model.state import GameState
from view.renderer import available_actions


def build_observation(state: GameState, player_index: int) -> dict:
    """Build the observation dict for the player at player_index.

    Returns a JSON-serialisable dict with everything that player can legally
    see, plus a pre-built list of action labels indexed 0..N-1.
    """
    player = state.players[player_index]
    actions = available_actions(state)

    return {
        # ── Identity ──────────────────────────────────────────────
        "player_index": player_index,
        "player_name":  player.name,

        # ── Turn state ────────────────────────────────────────────
        "phase":    state.phase.name,          # "BUY" or "PLAY"
        "deck_size": len(state.deck),

        # ── Your private information ───────────────────────────────
        "your_money":     player.money,
        "your_hand":      [_card(c) for c in player.hand],
        "your_tableau":   [_card(c) for c in player.tableau],
        "your_am_tokens": [
            cid for cid, holder in state.am_tokens.items()
            if holder is player
        ],

        # ── Public market ─────────────────────────────────────────
        "market": [
            {
                "company_id":   slot.card.company.id,
                "company_name": slot.card.company.name,
                "color":        slot.card.company.color,
                "coin_value":   slot.coin_value,
                # buyable = player does NOT hold the AM token for this company
                "buyable": state.am_tokens.get(slot.card.company.id) is not player,
            }
            for slot in state.market.slots
        ],

        # ── All AM tokens (public) ────────────────────────────────
        "am_tokens": {
            cid: holder.name if holder else None
            for cid, holder in state.am_tokens.items()
        },

        # ── Opponents (hand contents hidden) ─────────────────────
        "opponents": [
            {
                "name":      p.name,
                "money":     p.money,
                "hand_size": len(p.hand),
                "tableau":   [_card(c) for c in p.tableau],
                "am_tokens": [
                    cid for cid, holder in state.am_tokens.items()
                    if holder is p
                ],
            }
            for p in state.players
            if p is not player
        ],

        # ── Legal actions (agent picks an index) ──────────────────
        "actions": [a.label for a in actions],
    }


def build_result(state: GameState) -> dict:
    """Serialise the final GameResult for on_game_over notifications."""
    result = state.result
    if result is None:
        return {}
    return {
        "winner":     result.winner,
        "standings":  result.final_standings,   # list of (name, money) tuples
        "companies":  [
            {
                "name":        cr.company_name,
                "leader":      cr.leader.name if cr.leader else None,
                "card_counts": cr.card_counts,
            }
            for cr in result.company_results
        ],
    }


# ── Private helpers ───────────────────────────────────────────────

def _card(card: Card) -> dict:
    return {
        "company_id":   card.company.id,
        "company_name": card.company.name,
        "color":        card.company.color,
        "number":       card.number,
    }
