# tests/test_loader.py
# Constructs the GameBox from game_box.yaml and prints every component.
# Run with:  python -m tests.test_loader   (from the project root)

from collections import Counter

from model.loader import load_game_box


def main():
    box = load_game_box()

    # ── Meta ──────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  {box.meta['name']}  (v{box.meta['version']})")
    print(f"  Published by {box.meta['publisher']}")
    print(f"  Players: {box.meta['min_players']}–{box.meta['max_players']}")
    print(f"{'='*50}")

    # ── Companies ─────────────────────────────────────────────────
    print(f"\nCOMPANIES  ({len(box.companies)} total)")
    print(f"  {'ID':<12} {'Name':<30} {'Color':<10} Cards")
    print(f"  {'-'*60}")
    for c in box.companies:
        print(f"  {c.id:<12} {c.name:<30} {c.color:<10} {c.card_count}")

    # ── Deck ──────────────────────────────────────────────────────
    print(f"\nDECK  ({len(box.deck)} cards total)")
    for company in box.companies:
        cards = [card for card in box.deck.cards if card.company.id == company.id]
        nums = ", ".join(str(card.number) for card in cards)
        print(f"  {company.name:<30} [{nums}]")

    # ── Anti-Monopoly Chips ───────────────────────────────────────
    print(f"\nANTI-MONOPOLY CHIPS  ({len(box.anti_monopoly_chips)} total)")
    for chip in box.anti_monopoly_chips:
        print(f"  {chip}")

    # ── Coins ─────────────────────────────────────────────────────
    print(f"\nCOINS  ({len(box.coins)} total)")
    counts = Counter(coin.denomination for coin in box.coins)
    for denom in sorted(counts):
        print(f"  {counts[denom]:>3}x  {denom}-coin")
    print(f"  Starting money per player: {box.starting_money}")

    print(f"\n{box}\n")


if __name__ == "__main__":
    main()
