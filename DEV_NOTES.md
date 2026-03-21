# StartUps — Development Notes

## Goal
CLI replica of the Oink Games board game *StartUps* (3–6 players).

## Architecture
Game-View-Controller pattern, mirroring SplendorDuel:
- `model/` — game state, rules logic, entities (cards, players, chips, market)
- `view/` — CLI display (terminal rendering, no pygame)
- `controller/` — turn flow, input handling, action validation
- `tests/` — pytest unit tests per component
- `docs/` — rulebook and design notes

## Key Differences from SplendorDuel
- **CLI only** (no pygame/assets)
- Simpler state machine — single round, linear turn order
- Core complexity is in scoring and the Anti-Monopoly chip logic

## UI Design
Library stack: `rich` (rendering) + `readchar` (arrow key input)

### Horizontal Panel Carousel
Left/right arrows pan between panels. Panel count = 2 + number of players.

| Panel | Name | Content | Interactive? |
|---|---|---|---|
| 1 | Game Session | Game name, version, current turn, stage, save/load/quit | S / L / Q keys |
| 2 | Market | Deck count, market cards + coins, all Anti-Monopoly chips | Read-only |
| 3 | Current Player | Hand, tableau, chip held, action menu | ↑↓ select, ↵ confirm |
| 4+ | Other Players | Tableau only, hand hidden, money visible | Read-only |

### Panel Navigation
- `◀ / ▶` shown at top of every panel indicating position (e.g. `2 / 5`)
- Only the current player's panel has an interactive action menu
- Other players' hands are always hidden

## Development Order (planned)
1. Model — cards, deck, market, player, game state
2. Controller — turn actions, validation, game loop
3. View — panel rendering, carousel navigation
4. Tests — alongside each layer

## Open Questions
- Exact card counts per company (need to verify against physical game)
- Companies and their names/order for scoring
