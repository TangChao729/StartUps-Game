# model/save_load.py
# Serialise / deserialise GameState to/from YAML save files.
# Save files are stored in  saves/  at the project root.

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from model.loader import GameBox
from model.pieces import Card, Coin
from model.state import (
    GamePhase,
    GameState,
    Market,
    MarketSlot,
    Player,
    TurnPhase,
)

SAVES_DIR = Path(__file__).parent.parent / "saves"


# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def _card_to_dict(card: Card) -> dict:
    return {"company_id": card.company.id, "number": card.number}


def _coins_to_list(coins: list[Coin]) -> list[int]:
    return [c.denomination for c in coins]


def _sanitise_name(name: str) -> str:
    """Strip characters that are invalid in file names."""
    invalid = set('/\\:*?"<>|')
    return "".join(c if c not in invalid else "_" for c in name).strip("_") or "save"


# ──────────────────────────────────────────────────────────────────
# SAVE
# ──────────────────────────────────────────────────────────────────

def save_game(state: GameState, name: str) -> Path:
    """Serialise state to  saves/<name>.yaml  and return the path."""
    SAVES_DIR.mkdir(exist_ok=True)
    name = _sanitise_name(name)

    data = {
        "save_name":  name,
        "saved_at":   datetime.now().isoformat(timespec="seconds"),
        "game_phase": state.game_phase.name,
        "turn_phase": state.phase.name,
        "current_player_index":       state.current_player_index,
        "last_market_buy_company_id": state.last_market_buy_company_id,

        "removed_cards": [_card_to_dict(c) for c in state.removed_cards],
        "deck":          [_card_to_dict(c) for c in state.deck],

        "market": {
            "slots": [
                {
                    "card":  _card_to_dict(slot.card),
                    "coins": _coins_to_list(slot.coins),
                }
                for slot in state.market.slots
            ]
        },

        "am_tokens": {
            cid: (holder.name if holder else None)
            for cid, holder in state.am_tokens.items()
        },

        "players": [
            {
                "name":    p.name,
                "coins":   _coins_to_list(p.coins),
                "hand":    [_card_to_dict(c) for c in p.hand],
                "tableau": [_card_to_dict(c) for c in p.tableau],
            }
            for p in state.players
        ],

        "history": state.history,
    }

    path = SAVES_DIR / f"{name}.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return path


# ──────────────────────────────────────────────────────────────────
# LOAD
# ──────────────────────────────────────────────────────────────────

def load_game(path: Path, box: GameBox) -> GameState:
    """Deserialise a save file and return a fully reconstructed GameState."""
    with open(path) as f:
        data = yaml.safe_load(f)

    company_map = {c.id: c for c in box.companies}

    def make_card(d: dict) -> Card:
        return Card(company=company_map[d["company_id"]], number=d["number"])

    def make_coins(denoms: list[int]) -> list[Coin]:
        return [Coin(d) for d in (denoms or [])]

    players = [
        Player(
            name    = p["name"],
            hand    = [make_card(c) for c in p.get("hand", [])],
            tableau = [make_card(c) for c in p.get("tableau", [])],
            coins   = make_coins(p.get("coins", [])),
        )
        for p in data["players"]
    ]
    player_map = {p.name: p for p in players}

    am_tokens = {
        cid: (player_map.get(name) if name else None)
        for cid, name in data.get("am_tokens", {}).items()
    }

    market = Market(slots=[
        MarketSlot(
            card  = make_card(s["card"]),
            coins = make_coins(s.get("coins", [])),
        )
        for s in data["market"]["slots"]
    ])

    return GameState(
        players       = players,
        deck          = [make_card(c) for c in data.get("deck", [])],
        market        = market,
        companies     = box.companies,
        meta          = box.meta,
        removed_cards = [make_card(c) for c in data.get("removed_cards", [])],
        am_tokens     = am_tokens,
        current_player_index       = data.get("current_player_index", 0),
        phase                      = TurnPhase[data.get("turn_phase", "BUY")],
        game_phase                 = GamePhase[data.get("game_phase", "PLAYING")],
        last_market_buy_company_id = data.get("last_market_buy_company_id"),
        history                    = data.get("history", []),
    )


# ──────────────────────────────────────────────────────────────────
# LIST
# ──────────────────────────────────────────────────────────────────

def list_saves() -> list[Path]:
    """Return all .yaml save files, newest first."""
    if not SAVES_DIR.exists():
        return []
    return sorted(
        SAVES_DIR.glob("*.yaml"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def default_save_name() -> str:
    return datetime.now().strftime("save_%Y-%m-%d_%H-%M-%S")
