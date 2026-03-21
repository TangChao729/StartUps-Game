# tests/test_state.py
# Tests for GameState mechanics: coin costs, AM tokens, and scoring.
# Run with:  python -m tests.test_state   (from the project root)

from model.loader import load_game_box
from model.pieces import Card, Coin
from model.state import (
    GamePhase, GameState, Market, MarketSlot, Player, TurnPhase, new_game
)


# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def header(title: str) -> None:
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


def show_state(state: GameState) -> None:
    print(f"\n  {state}")
    print(f"  Market : {state.market}")
    for p in state.players:
        marker = " ◀" if p is state.current_player else "  "
        am = [cid for cid, holder in state.am_tokens.items() if holder is p]
        am_str = f"  AM:{am}" if am else ""
        print(f"  {marker} {p}{am_str}")
        print(f"       hand   : {p.hand}")
        print(f"       tableau: {p.tableau}")


# ──────────────────────────────────────────────────────────────────
# SCENARIO 1 — Coin cost when buying from deck
# ──────────────────────────────────────────────────────────────────

def test_buy_cost():
    header("SCENARIO 1: Coin cost when buying from deck")

    box = load_game_box()
    companies = box.companies

    alice = Player("Alice", coins=[Coin(1)] * 10)
    bob   = Player("Bob",   coins=[Coin(1)] * 10)

    # Seed the market with two cards (different companies)
    market = Market(slots=[
        MarketSlot(card=Card(companies[0], 1)),   # company_a card
        MarketSlot(card=Card(companies[1], 1)),   # company_b card
    ])

    # Give deck one card
    deck = [Card(companies[2], 1)]

    state = GameState(
        players=[alice, bob],
        deck=deck,
        market=market,
        companies=companies,
        am_tokens={c.id: None for c in companies},
    )

    show_state(state)

    # Alice draws from deck — 2 purchasable market cards → costs $2
    print("\n  Alice draws from deck (market has 2 purchasable cards → costs $2)")
    state.buy_from_deck()

    assert alice.money == 8, f"Expected $8, got ${alice.money}"
    assert market.slots[0].coin_value == 1
    assert market.slots[1].coin_value == 1
    print(f"  Alice money: ${alice.money}  (expected $8) ✓")
    print(f"  Market slots after draw: {market.slots}")

    # Alice plays the card (index 3 = last card added to hand) as investment
    state.play_as_investment(len(alice.hand) - 1)

    # Bob draws — market still has 2 cards, Bob can purchase both → costs $2
    print("\n  Bob draws from deck — BUT deck is now empty, so game ends at end of Bob's turn")
    # Actually the deck has 0 cards now since Alice drew it. Let's check
    print(f"  Deck size: {len(state.deck)}")

    print("\n  [OK] Coin cost scenario passed")


# ──────────────────────────────────────────────────────────────────
# SCENARIO 2 — AM token assignment and market restriction
# ──────────────────────────────────────────────────────────────────

def test_am_tokens():
    header("SCENARIO 2: AM token assignment and market restriction")

    box = load_game_box()
    companies = box.companies
    company_a = companies[0]

    alice = Player("Alice", coins=[Coin(1)] * 10)
    bob   = Player("Bob",   coins=[Coin(1)] * 10)

    # Deck has several cards; market has a company_a card
    deck   = [Card(company_a, 2)] + [Card(companies[2], i) for i in range(1, 10)]
    market = Market(slots=[MarketSlot(card=Card(company_a, 3))])

    state = GameState(
        players=[alice, bob],
        deck=deck,
        market=market,
        companies=companies,
        am_tokens={c.id: None for c in companies},
    )

    # --- Alice draws and plays company_a card as investment ---
    print("\n  Alice draws company_a #2 from deck (1 purchasable market slot → pays $1)")
    state.buy_from_deck()
    assert alice.money == 9
    assert market.slots[0].coin_value == 1

    drawn = alice.hand[-1]
    print(f"  Alice drew: {drawn}")
    state.play_as_investment(alice.hand.index(drawn))

    token_holder = state.am_tokens.get(company_a.id)
    print(f"  AM token for {company_a.name}: {token_holder.name if token_holder else 'None'}")
    assert token_holder is alice, "Alice should hold AM token after investing first"
    print("  Alice holds AM token ✓")

    show_state(state)

    # --- Bob tries to buy company_a from market — should be ALLOWED (Bob has no AM token) ---
    print("\n  Bob buys company_a #3 from market (Bob has no AM token → allowed)")
    bought = state.buy_from_market(0)
    assert bought.company.id == company_a.id
    assert bob.money == 10 + 1  # got the stacked $1 coin from Alice's deck draw
    print(f"  Bob bought: {bought}, money now: ${bob.money}  (collected stacked coin) ✓")

    state.play_as_investment(0)
    # Bob now has 1 company_a card, Alice also has 1 — tied, no token transfer
    assert state.am_tokens[company_a.id] is alice, "Tie: token stays with Alice ✓"
    print(f"  After tie: AM token still with Alice ✓")

    # Now give Alice another company_a investment so she has 2, Bob has 1
    alice.tableau.append(Card(company_a, 4))
    state._update_am_token(company_a.id, alice)
    assert state.am_tokens[company_a.id] is alice
    print(f"  Alice invests another: AM token stays with Alice (2 vs 1) ✓")

    # Give Bob another investment so Bob has 2, Alice has 2 — still tied
    bob.tableau.append(Card(company_a, 5))
    state._update_am_token(company_a.id, bob)
    assert state.am_tokens[company_a.id] is alice, "Still tied: no transfer ✓"
    print(f"  Bob also has 2: still tied, Alice keeps token ✓")

    # Bob invests one more: Bob has 3, Alice has 2 — Bob takes token
    bob.tableau.append(Card(company_a, 6))
    state._update_am_token(company_a.id, bob)
    assert state.am_tokens[company_a.id] is bob
    print(f"  Bob invests one more (3 vs 2): AM token transfers to Bob ✓")

    print("\n  [OK] AM token scenario passed")


# ──────────────────────────────────────────────────────────────────
# SCENARIO 3 — Full scoring
# ──────────────────────────────────────────────────────────────────

def test_scoring():
    header("SCENARIO 3: Full scoring")

    box = load_game_box()
    companies = box.companies
    company_a = companies[0]   # Giraffe Beer
    company_b = companies[1]   # Bowwow Games

    alice   = Player("Alice",   coins=[Coin(1)] * 10)
    bob     = Player("Bob",     coins=[Coin(1)] * 10)
    charlie = Player("Charlie", coins=[Coin(1)] * 10)

    # Manually set tableaux
    # company_a: Alice=3, Bob=1, Charlie=1  → Alice is leader
    # company_b: Bob=2, Charlie=1           → Bob is leader
    alice.tableau   = [Card(company_a, i) for i in range(1, 4)]          # 3 cards
    bob.tableau     = [Card(company_a, 4), Card(company_b, 1), Card(company_b, 2)]
    charlie.tableau = [Card(company_a, 5), Card(company_b, 3)]

    # Give each player some hand cards (will be folded into tableau at scoring)
    alice.hand   = [Card(company_b, 4)]    # +1 company_b for Alice
    bob.hand     = []
    charlie.hand = []

    state = GameState(
        players=[alice, bob, charlie],
        deck=[],   # empty deck triggers scoring on next _end_turn
        market=Market(),
        companies=companies,
        am_tokens={
            company_a.id: alice,   # Alice holds company_a AM token
            company_b.id: bob,     # Bob holds company_b AM token
            **{c.id: None for c in companies if c.id not in (company_a.id, company_b.id)},
        },
    )

    print("\n  Pre-scoring state:")
    show_state(state)

    result = state.score_game()

    print(f"\n{result}")

    # --- Verify scoring ---
    # Hand reveal folds Alice's company_b #4 into her tableau.
    # company_a (Giraffe Beer): Alice=3, Bob=1, Charlie=1 → Alice leads
    #   Bob pays $1 → Alice gains $3; Charlie pays $1 → Alice gains $3
    # company_b (Bowwow Games): Alice=1, Bob=2, Charlie=1 → Bob leads
    #   Alice pays $1 → Bob gains $3; Charlie pays $1 → Bob gains $3
    #
    # Alice:   10 + 6 (company_a gains) - 1 (company_b pay)  = $15
    # Bob:     10 - 1 (company_a pay)   + 6 (company_b gains) = $15
    # Charlie: 10 - 1 (company_a pay)   - 1 (company_b pay)  = $8

    print(f"\n  Alice money: ${alice.money}")
    print(f"  Bob   money: ${bob.money}")
    print(f"  Charlie money: ${charlie.money}")

    assert alice.money   == 15, f"Alice expected $15, got ${alice.money}"
    assert bob.money     == 15, f"Bob expected $15, got ${bob.money}"
    assert charlie.money == 8,  f"Charlie expected $8, got ${charlie.money}"

    assert state.game_phase == GamePhase.GAME_OVER
    assert result.winner == "Alice"
    print(f"\n  Winner: {result.winner} ✓")
    print("\n  [OK] Scoring scenario passed")


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_buy_cost()
    test_am_tokens()
    test_scoring()
    print("\n  All scenarios passed.\n")
