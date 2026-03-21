# model/loader.py
# Reads game_box.yaml and constructs all game piece objects.

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from model.pieces import AntiMonopolyChip, Card, Coin, Company, Deck

GAME_BOX_PATH = Path(__file__).parent.parent / "game_box.yaml"


@dataclass
class GameBox:
    """All components that come in the box, ready to play with."""
    meta: dict
    companies: list[Company]
    deck: Deck
    anti_monopoly_chips: list[AntiMonopolyChip]
    coins: list[Coin]
    starting_money: int = 0

    def __repr__(self) -> str:
        return (
            f"GameBox("
            f"{self.meta['name']!r}, "
            f"{len(self.companies)} companies, "
            f"{len(self.deck)} cards, "
            f"{len(self.anti_monopoly_chips)} chips, "
            f"{len(self.coins)} coins)"
        )


def load_game_box(path: str | Path = GAME_BOX_PATH) -> GameBox:
    """Parse game_box.yaml and return a fully constructed GameBox."""
    with open(path) as f:
        data = yaml.safe_load(f)

    # --- Companies ---
    companies: list[Company] = [
        Company(
            id=c["id"],
            name=c["name"],
            color=c["color"],
            card_count=c["card_count"],
        )
        for c in data["companies"]
    ]

    # --- Cards (one per number 1..card_count, per company) ---
    all_cards: list[Card] = [
        Card(company=company, number=n)
        for company in companies
        for n in range(1, company.card_count + 1)
    ]
    deck = Deck(all_cards)

    # --- Anti-monopoly chips (one per company) ---
    chips: list[AntiMonopolyChip] = [
        AntiMonopolyChip(company=company)
        for company in companies
    ]

    # --- Coins ---
    coin_data = data["coins"]
    coins: list[Coin] = [
        Coin(denomination=denom)
        for denom, count in coin_data["total_per_denomination"].items()
        for _ in range(count)
    ]

    return GameBox(
        meta=data["meta"],
        companies=companies,
        deck=deck,
        anti_monopoly_chips=chips,
        coins=coins,
        starting_money=coin_data["starting_money"],
    )
