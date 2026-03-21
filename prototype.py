"""
StartUps — UI Prototype
5-panel horizontal carousel with keyboard navigation.
"""

import readchar
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich import box
import os
import sys

console = Console()

# ── Prototype state ────────────────────────────────────────────────────────────

SAVE_FILE = "000"

PANELS = ["Game Session", "Market", "Taylor (You)", "Player 2", "Player 3"]

GAME_SESSION_OPTIONS = ["Save Game", "Load Game", "Quit"]

# ── Panel renderers ────────────────────────────────────────────────────────────

def nav_bar(current: int, total: int) -> Text:
    t = Text(justify="center")
    t.append("◀  ", style="bold cyan")
    t.append(f"{current} / {total}", style="bold white")
    t.append("  ▶", style="bold cyan")
    return t


def render_game_session(selected: int) -> Panel:
    lines = Text()
    lines.append("StartUps", style="bold magenta")
    lines.append("                        v0.1\n", style="dim")
    lines.append("\n")
    lines.append("Players:      ", style="dim")
    lines.append("3\n", style="white")
    lines.append("Current Turn: ", style="dim")
    lines.append("Taylor\n", style="white")
    lines.append("Stage:        ", style="dim")
    lines.append("Draw Phase\n", style="white")
    lines.append("\n")
    lines.append("─" * 36 + "\n", style="dim")
    lines.append("\n")

    for i, option in enumerate(GAME_SESSION_OPTIONS):
        if i == selected:
            lines.append(f"  ▶ {option}\n", style="bold yellow")
        else:
            lines.append(f"    {option}\n", style="white")

    lines.append("\n")
    lines.append("↑↓ select   ↵ confirm\n", style="dim italic")

    return Panel(
        lines,
        title=nav_bar(1, len(PANELS)),
        title_align="center",
        subtitle="[dim]Game Session[/dim]",
        box=box.DOUBLE,
        border_style="cyan",
        width=42,
        padding=(0, 1),
    )


def render_market() -> Panel:
    lines = Text()
    lines.append("Deck: ", style="dim")
    lines.append("18 cards remaining\n", style="white")
    lines.append("\n")
    lines.append("Market\n", style="bold")
    lines.append("─" * 36 + "\n", style="dim")
    lines.append(f"{'Company':<16}{'Coins':>6}  {'Locked?':>8}\n", style="dim")
    lines.append(f"{'Octocoffee':<16}{'2':>6}  {'no':>8}\n", style="white")
    lines.append(f"{'Giraffe Beer':<16}{'0':>6}  {'no':>8}\n", style="white")
    lines.append(f"{'EMT':<16}{'5':>6}  {'YES ★':>8}\n", style="yellow")
    lines.append(f"{'(empty)':<16}\n", style="dim")
    lines.append("\n")
    lines.append("Anti-Monopoly Chips\n", style="bold")
    lines.append("─" * 36 + "\n", style="dim")
    lines.append(f"{'Octocoffee':<16}→  Taylor\n", style="white")
    lines.append(f"{'Giraffe Beer':<16}→  (none)\n", style="dim")
    lines.append(f"{'EMT':<16}→  Player 2\n", style="white")
    lines.append(f"{'Bowwow':<16}→  (none)\n", style="dim")
    lines.append(f"{'Crowdfund':<16}→  (none)\n", style="dim")
    lines.append(f"{'RocketRide':<16}→  (none)\n", style="dim")

    return Panel(
        lines,
        title=nav_bar(2, len(PANELS)),
        title_align="center",
        subtitle="[dim]Market[/dim]",
        box=box.DOUBLE,
        border_style="cyan",
        width=42,
        padding=(0, 1),
    )


def render_current_player() -> Panel:
    lines = Text()
    lines.append("Taylor", style="bold green")
    lines.append("                      💰 10\n", style="yellow")
    lines.append("\n")
    lines.append("Hand:\n", style="bold")
    lines.append("  Octocoffee  Octocoffee  EMT\n", style="white")
    lines.append("\n")
    lines.append("Tableau:\n", style="bold")
    lines.append("  Octocoffee x2    ★ (chip held)\n", style="white")
    lines.append("  Giraffe Beer x1\n", style="white")
    lines.append("\n")
    lines.append("─" * 36 + "\n", style="dim")
    lines.append("Actions", style="bold")
    lines.append("          ↑↓ select  ↵ go\n", style="dim italic")
    lines.append("  ▶ Draw from deck       (18 left)\n", style="bold yellow")
    lines.append("    Take Giraffe Beer    (0 coins)\n", style="white")
    lines.append("    Take Octocoffee      (2 coins)\n", style="white")

    return Panel(
        lines,
        title=nav_bar(3, len(PANELS)),
        title_align="center",
        subtitle="[dim]Taylor (You)[/dim]",
        box=box.DOUBLE,
        border_style="green",
        width=42,
        padding=(0, 1),
    )


def render_other_player(panel_index: int, name: str, money: int, tableau: list) -> Panel:
    lines = Text()
    lines.append(f"{name}", style="bold white")
    money_pad = 42 - len(name) - 10
    lines.append(" " * money_pad + f"💰 {money}\n", style="yellow")
    lines.append("\n")
    lines.append("Hand:    ", style="dim")
    lines.append("3 cards (hidden)\n", style="dim italic")
    lines.append("\n")
    lines.append("Tableau:\n", style="bold")
    for entry in tableau:
        lines.append(f"  {entry}\n", style="white")

    return Panel(
        lines,
        title=nav_bar(panel_index, len(PANELS)),
        title_align="center",
        subtitle=f"[dim]{name}[/dim]",
        box=box.DOUBLE,
        border_style="cyan",
        width=42,
        padding=(0, 1),
    )


# ── Dummy data for other players ───────────────────────────────────────────────

OTHER_PLAYERS = [
    {"name": "Player 2", "money": 7,  "tableau": ["EMT x3           ★ (chip held)", "Giraffe Beer x1"]},
    {"name": "Player 3", "money": 12, "tableau": ["Giraffe Beer x2", "Octocoffee x1"]},
]

# ── Draw helpers ───────────────────────────────────────────────────────────────

def clear():
    os.system("clear")


def draw(panel_index: int, session_selected: int, message: str = ""):
    clear()
    if panel_index == 0:
        panel = render_game_session(session_selected)
    elif panel_index == 1:
        panel = render_market()
    elif panel_index == 2:
        panel = render_current_player()
    else:
        p = OTHER_PLAYERS[panel_index - 3]
        panel = render_other_player(panel_index + 1, p["name"], p["money"], p["tableau"])

    console.print(panel)

    if message:
        console.print(f"\n  [bold green]{message}[/bold green]")
    else:
        console.print("\n  [dim]← → navigate panels[/dim]")


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    panel_index = 0
    session_selected = 0
    message = ""

    draw(panel_index, session_selected)

    while True:
        key = readchar.readkey()

        message = ""  # clear message on any keypress

        # ── Left / Right — panel navigation ───────────────────────────────────
        if key == readchar.key.LEFT:
            panel_index = (panel_index - 1) % len(PANELS)

        elif key == readchar.key.RIGHT:
            panel_index = (panel_index + 1) % len(PANELS)

        # ── Up / Down — only on Game Session panel ─────────────────────────────
        elif key == readchar.key.UP:
            if panel_index == 0:
                session_selected = (session_selected - 1) % len(GAME_SESSION_OPTIONS)

        elif key == readchar.key.DOWN:
            if panel_index == 0:
                session_selected = (session_selected + 1) % len(GAME_SESSION_OPTIONS)

        # ── Enter — confirm action on Game Session panel ───────────────────────
        elif key == readchar.key.ENTER:
            if panel_index == 0:
                option = GAME_SESSION_OPTIONS[session_selected]

                if option == "Save Game":
                    message = f"Game saved as {SAVE_FILE}"

                elif option == "Load Game":
                    message = f"Loaded game session {SAVE_FILE}"

                elif option == "Quit":
                    clear()
                    console.print("[bold red]Goodbye![/bold red]")
                    sys.exit(0)

        draw(panel_index, session_selected, message)


if __name__ == "__main__":
    main()
