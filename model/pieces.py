# model/pieces.py
# All physical game piece classes for StartUps.


class Piece:
    """Base class for every physical component in the game box."""
    pass


# ------------------------------------------------------------------
# COMPANY  (metadata — not a holdable piece, but a category)
# ------------------------------------------------------------------

class Company:
    def __init__(self, id: str, name: str, color: str, card_count: int):
        self.id = id
        self.name = name
        self.color = color
        self.card_count = card_count

    def __repr__(self) -> str:
        return f"Company({self.name!r}, color={self.color}, cards={self.card_count})"


# ------------------------------------------------------------------
# CARD
# ------------------------------------------------------------------

class Card(Piece):
    """A single share card belonging to a company."""

    def __init__(self, company: Company, number: int):
        self.company = company   # reference to the Company object
        self.number = number     # position within the company (1-based)

    @property
    def color(self) -> str:
        return self.company.color

    def __repr__(self) -> str:
        return f"Card({self.company.name!r} #{self.number})"


# ------------------------------------------------------------------
# ANTI-MONOPOLY CHIP
# ------------------------------------------------------------------

class AntiMonopolyChip(Piece):
    """One chip per company; activated when a monopoly forms."""

    def __init__(self, company: Company):
        self.company = company

    @property
    def color(self) -> str:
        return self.company.color

    def __repr__(self) -> str:
        return f"AntiMonopolyChip({self.company.name!r})"


# ------------------------------------------------------------------
# COIN
# ------------------------------------------------------------------

class Coin(Piece):
    """A single coin of a given denomination."""

    def __init__(self, denomination: int):
        self.denomination = denomination

    def __repr__(self) -> str:
        return f"Coin({self.denomination})"


# ------------------------------------------------------------------
# DECK  (container — not a holdable piece)
# ------------------------------------------------------------------

class Deck:
    """The face-down draw pile: an ordered list of Cards."""

    def __init__(self, cards: list[Card]):
        self.cards: list[Card] = list(cards)

    def __len__(self) -> int:
        return len(self.cards)

    def __repr__(self) -> str:
        return f"Deck({len(self.cards)} cards)"
