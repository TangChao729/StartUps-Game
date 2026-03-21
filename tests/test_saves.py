import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.loader import load_game_box
from model.save_load import load_game

SAVES_DIR = Path(__file__).parent.parent / "saves"

box = load_game_box()


def print_result(title, result):
    print(f'=== {title} ===')
    for cr in result.company_results:
        leader = cr.leader.name if cr.leader else 'TIED (no payments)'
        counts = ', '.join(f'{n}:{v}' for n, v in cr.card_counts.items() if v)
        print(f'  {cr.company_name}: leader={leader} [{counts}]')
    print()
    print('  Standings:', result.final_standings)
    print(f'  Winner:    {result.winner}')
    print()


# Scenario 1: Alice invests company_f #6 (trigger)
state1 = load_game(SAVES_DIR / 'test_1_clear_monopoly.yaml', box)
state1.play_as_investment(0)
print_result('Scenario 1: Clear Monopoly', state1.result)

# Scenario 2: Alice invests company_c #3 (trigger)
state2 = load_game(SAVES_DIR / 'test_2_mixed_monopoly.yaml', box)
state2.play_as_investment(0)
print_result('Scenario 2: Mixed Monopoly', state2.result)

# Scenario 3: Charlie trades company_f #10 to market (trigger)
state3 = load_game(SAVES_DIR / 'test_3_all_tied.yaml', box)
state3.play_to_market(0)
print_result('Scenario 3: All Tied', state3.result)
