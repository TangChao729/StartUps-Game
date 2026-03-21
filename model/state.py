# model/state.py
# Core game state and turn logic for StartUps.

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto

from model.loader import GameBox
from model.pieces import Card, Coin, Company


# ──────────────────────────────────────────────────────────────────
# ENUMS
# ──────────────────────────────────────────────────────────────────

class TurnPhase(Enum):
    BUY = auto()    # player must acquire a card
    PLAY = auto()   # player must play a card from hand


class GamePhase(Enum):
    PLAYING = auto()
    GAME_OVER = auto()


# ──────────────────────────────────────────────────────────────────
# MARKET SLOT  (card + any coins stacked on top of it)
# ──────────────────────────────────────────────────────────────────

@dataclass
class MarketSlot:
    """A face-up card in the open market, possibly with coins stacked on it."""
    card: Card
    coins: list[Coin] = field(default_factory=list)

    @property
    def coin_value(self) -> int:
        return sum(c.denomination for c in self.coins)

    def __repr__(self) -> str:
        if self.coins:
            return f"MarketSlot({self.card}, +${self.coin_value})"
        return f"MarketSlot({self.card})"


# ──────────────────────────────────────────────────────────────────
# PLAYER
# ──────────────────────────────────────────────────────────────────

@dataclass
class Player:
    name: str
    hand: list[Card] = field(default_factory=list)
    tableau: list[Card] = field(default_factory=list)   # personal investments
    coins: list[Coin] = field(default_factory=list)

    @property
    def money(self) -> int:
        return sum(c.denomination for c in self.coins)

    def card_count(self, company_id: str) -> int:
        """How many cards of this company the player has invested."""
        return sum(1 for c in self.tableau if c.company.id == company_id)

    def __repr__(self) -> str:
        return (
            f"Player({self.name!r}, "
            f"hand={len(self.hand)}, "
            f"tableau={len(self.tableau)}, "
            f"money=${self.money})"
        )


# ──────────────────────────────────────────────────────────────────
# MARKET
# ──────────────────────────────────────────────────────────────────

@dataclass
class Market:
    """The open trade row — face-up cards any player can purchase."""
    slots: list[MarketSlot] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.slots)

    def __repr__(self) -> str:
        if not self.slots:
            return "Market(empty)"
        return "Market([" + ", ".join(repr(s) for s in self.slots) + "])"


# ──────────────────────────────────────────────────────────────────
# SCORING RESULTS
# ──────────────────────────────────────────────────────────────────

@dataclass
class CompanyResult:
    company_name: str
    leader: Player | None
    card_counts: dict[str, int]   # player_name → count


@dataclass
class GameResult:
    company_results: list[CompanyResult]
    final_standings: list[tuple[str, int]]   # (player_name, money) sorted desc

    @property
    def winner(self) -> str:
        if not self.final_standings:
            return "Nobody"
        top_score = self.final_standings[0][1]
        winners = [name for name, money in self.final_standings if money == top_score]
        return " & ".join(winners)

    def __repr__(self) -> str:
        lines = ["=== GAME RESULT ==="]
        for cr in self.company_results:
            leader_name = cr.leader.name if cr.leader else "none"
            counts_str = ", ".join(
                f"{name}:{n}" for name, n in cr.card_counts.items() if n
            )
            lines.append(f"  {cr.company_name}: leader={leader_name}  [{counts_str}]")
        lines.append("  Final standings:")
        for i, (name, money) in enumerate(self.final_standings, 1):
            lines.append(f"    {i}. {name}  ${money}")
        lines.append(f"  Winner: {self.winner}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────
# GAME STATE
# ──────────────────────────────────────────────────────────────────

@dataclass
class GameState:
    players: list[Player]
    deck: list[Card]            # face-down draw pile
    market: Market
    companies: list[Company]
    # company_id → the Player who holds that AM token, or None
    meta: dict = field(default_factory=dict)
    removed_cards: list[Card] = field(default_factory=list)   # 5 cards set aside at game start
    am_tokens: dict[str, Player | None] = field(default_factory=dict)
    current_player_index: int = 0
    phase: TurnPhase = TurnPhase.BUY
    game_phase: GamePhase = GamePhase.PLAYING
    last_market_buy_company_id: str | None = None  # trade restriction this turn
    result: GameResult | None = None

    # ── Convenience ───────────────────────────────────────────────

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]

    # ── BUY-phase actions ─────────────────────────────────────────

    def buy_from_deck(self) -> Card:
        """Draw the top card from the deck.

        Cost: $1 deposited onto each market slot the player *could* buy
        (i.e. every market card whose company AM token they don't hold).
        If the market has no purchasable cards, drawing is free.
        """
        self._require_phase(TurnPhase.BUY)
        self._require_game_phase(GamePhase.PLAYING)
        if not self.deck:
            raise ValueError("The deck is empty.")

        player = self.current_player
        payable = self._purchasable_slots_for(player)
        cost = len(payable)

        if cost > 0:
            if player.money < cost:
                raise ValueError(
                    f"{player.name} needs ${cost} to draw (${1} per purchasable "
                    f"market card) but only has ${player.money}."
                )
            for slot in payable:
                slot.coins.append(self._take_coin(player, 1))

        card = self.deck.pop(0)
        player.hand.append(card)
        self.phase = TurnPhase.PLAY
        return card

    def buy_from_market(self, slot_index: int) -> Card:
        """Buy the card at the given market slot — free, and collect any stacked coins.

        Blocked if the player holds the AM token for that card's company.
        """
        self._require_phase(TurnPhase.BUY)
        self._require_game_phase(GamePhase.PLAYING)

        player = self.current_player
        if not (0 <= slot_index < len(self.market.slots)):
            raise IndexError(
                f"Market slot {slot_index} does not exist "
                f"(market has {len(self.market.slots)} slots)."
            )

        slot = self.market.slots[slot_index]
        if self.am_tokens.get(slot.card.company.id) is player:
            raise ValueError(
                f"{player.name} holds the AM token for "
                f"{slot.card.company.name!r} and cannot buy it from the market."
            )

        self.market.slots.pop(slot_index)
        player.hand.append(slot.card)
        player.coins.extend(slot.coins)   # collect stacked coins

        self.last_market_buy_company_id = slot.card.company.id
        self.phase = TurnPhase.PLAY
        return slot.card

    # ── PLAY-phase actions ────────────────────────────────────────

    def play_as_investment(self, hand_index: int) -> Card:
        """Place a card from hand onto the current player's tableau (investment).

        After placing, the AM token for that company is reassigned if needed.
        """
        self._require_phase(TurnPhase.PLAY)
        self._require_game_phase(GamePhase.PLAYING)

        player = self.current_player   # capture before _end_turn advances index
        card = self._pop_from_hand(hand_index)
        player.tableau.append(card)
        self._update_am_token(card.company.id, player)
        self._end_turn()
        return card

    def play_to_market(self, hand_index: int) -> Card:
        """Place a card from hand into the open market (available for others to buy).

        Cannot trade a card whose company was just bought from the market this turn.
        """
        self._require_phase(TurnPhase.PLAY)
        self._require_game_phase(GamePhase.PLAYING)

        card = self.current_player.hand[hand_index] if 0 <= hand_index < len(self.current_player.hand) else None
        if card and card.company.id == self.last_market_buy_company_id:
            raise ValueError(
                f"Cannot trade {card.company.name} — it was bought from the market this turn."
            )
        card = self._pop_from_hand(hand_index)
        self.market.slots.append(MarketSlot(card=card))
        self._end_turn()
        return card

    # ── Scoring ───────────────────────────────────────────────────

    def score_game(self) -> GameResult:
        """Triggered when deck is exhausted.

        1. All hand cards are added to each player's tableau.
        2. Per company: find the leader (most cards; AM token breaks ties).
           Non-leaders pay $1 per card; leader gains $3 per such card.
        3. Player with most coins wins.
        """
        # Step 1 — reveal hands
        for player in self.players:
            player.tableau.extend(player.hand)
            player.hand.clear()

        # Step 2 — score each company
        company_results: list[CompanyResult] = []

        for company in self.companies:
            counts = [(p, p.card_count(company.id)) for p in self.players]
            if not any(n for _, n in counts):
                continue

            # Find leader: strict majority wins outright; in a tie, the AM
            # token holder among the tied players breaks the deadlock.
            # If no tied player holds the AM token, nobody wins (no payments).
            max_count = max(n for _, n in counts)
            candidates = [p for p, n in counts if n == max_count]
            if len(candidates) == 1:
                leader = candidates[0]
            else:
                token_holder = self.am_tokens.get(company.id)
                if token_holder in candidates:
                    leader = token_holder
                else:
                    # True tie with no AM tiebreak — record result, skip payments
                    company_results.append(CompanyResult(
                        company_name=company.name,
                        leader=None,
                        card_counts={p.name: n for p, n in counts},
                    ))
                    continue

            # Transfer coins: non-leaders pay $1/card; leader gains $3/card
            for player, count in counts:
                if player is leader or count == 0:
                    continue
                for _ in range(count):
                    try:
                        leader.coins.append(Coin(3))
                        self._take_coin(player, 1)
                    except ValueError:
                        # Player has no $1 coin — remove the $3 we pre-added
                        leader.coins.pop()

            company_results.append(CompanyResult(
                company_name=company.name,
                leader=leader,
                card_counts={p.name: n for p, n in counts},
            ))

        # Step 3 — final standings
        standings = sorted(
            [(p.name, p.money) for p in self.players],
            key=lambda x: -x[1],
        )

        self.result = GameResult(
            company_results=company_results,
            final_standings=standings,
        )
        self.game_phase = GamePhase.GAME_OVER
        return self.result

    # ── Private helpers ───────────────────────────────────────────

    def _purchasable_slots_for(self, player: Player) -> list[MarketSlot]:
        """Market slots this player is allowed to buy (no AM token block)."""
        return [
            slot for slot in self.market.slots
            if self.am_tokens.get(slot.card.company.id) is not player
        ]

    def _update_am_token(self, company_id: str, played_by: Player) -> None:
        """Give played_by the AM token if they now have strictly the most cards."""
        played_by_count = played_by.card_count(company_id)
        others_max = max(
            (p.card_count(company_id) for p in self.players if p is not played_by),
            default=0,
        )
        if played_by_count > others_max:
            self.am_tokens[company_id] = played_by

    def _take_coin(self, player: Player, denomination: int) -> Coin:
        """Remove and return one coin of the exact denomination from the player."""
        for i, coin in enumerate(player.coins):
            if coin.denomination == denomination:
                return player.coins.pop(i)
        raise ValueError(
            f"{player.name} has no ${denomination} coin (money=${player.money})."
        )

    def _pop_from_hand(self, hand_index: int) -> Card:
        hand = self.current_player.hand
        if not (0 <= hand_index < len(hand)):
            raise IndexError(
                f"Hand index {hand_index} out of range "
                f"(hand has {len(hand)} cards)."
            )
        return hand.pop(hand_index)

    def _require_phase(self, expected: TurnPhase) -> None:
        if self.phase != expected:
            raise ValueError(
                f"Requires {expected.name} phase but current phase is {self.phase.name}."
            )

    def _require_game_phase(self, expected: GamePhase) -> None:
        if self.game_phase != expected:
            raise ValueError(
                f"Game is {self.game_phase.name}, expected {expected.name}."
            )

    def _end_turn(self) -> None:
        self.current_player_index = (
            (self.current_player_index + 1) % len(self.players)
        )
        self.phase = TurnPhase.BUY
        self.last_market_buy_company_id = None
        if not self.deck:
            self.score_game()

    def __repr__(self) -> str:
        if self.game_phase == GamePhase.GAME_OVER:
            winner = self.result.winner if self.result else "?"
            return f"GameState(GAME_OVER, winner={winner!r})"
        return (
            f"GameState("
            f"turn={self.current_player.name!r}, "
            f"phase={self.phase.name}, "
            f"deck={len(self.deck)}, "
            f"market={len(self.market)} cards)"
        )


# ──────────────────────────────────────────────────────────────────
# FACTORY
# ──────────────────────────────────────────────────────────────────

def new_game(box: GameBox, player_names: list[str]) -> GameState:
    """Build a fresh GameState from a GameBox and player names."""
    min_p, max_p = box.meta["min_players"], box.meta["max_players"]
    if not (min_p <= len(player_names) <= max_p):
        raise ValueError(
            f"StartUps requires {min_p}–{max_p} players, got {len(player_names)}."
        )

    deck: list[Card] = list(box.deck.cards)
    random.shuffle(deck)

    # Remove 5 random cards and set them aside (rule requirement)
    removed_cards: list[Card] = [deck.pop(0) for _ in range(5)]

    players: list[Player] = [
        Player(
            name=name,
            hand=[deck.pop(0) for _ in range(3)],
            coins=[Coin(1) for _ in range(box.starting_money)],
        )
        for name in player_names
    ]

    return GameState(
        players=players,
        deck=deck,
        market=Market(),
        companies=box.companies,
        removed_cards=removed_cards,
        meta=box.meta,
        am_tokens={c.id: None for c in box.companies},
    )
