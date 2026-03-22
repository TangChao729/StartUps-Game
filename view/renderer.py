# view/renderer.py
# All rendering logic for the StartUps terminal UI.

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, NamedTuple

from rich import box as rbox
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from model.pieces import Card
from model.state import GamePhase, GameState, TurnPhase

PANEL_WIDTH  = 52
_SEP         = "─" * (PANEL_WIDTH - 8)   # separator that fits inside the panel
MIN_PLAYERS  = 3
MAX_PLAYERS  = 7

COMPANY_COLOR: dict[str, str] = {
    "orange":  "orange3",
    "blue":    "bright_blue",
    "pink":    "bright_magenta",
    "coffee":  "gold1",
    "green":   "green3",
    "red":     "bright_red",
}

_SESSION_OPTIONS   = ["New Game", "Save Game", "Load Game", "Quit"]
_CONFIRM_OPTIONS   = ["Yes, start new game", "No, go back"]
_OVER_OPTIONS    = ["Play Again", "Quit"]


# ──────────────────────────────────────────────────────────────────
# ACTIONS
# ──────────────────────────────────────────────────────────────────

class Action(NamedTuple):
    label: str
    execute: Callable[[], object]


def available_actions(state: GameState) -> list[Action]:
    """Build the legal action list for the current player."""
    player = state.current_player
    actions: list[Action] = []

    if state.phase == TurnPhase.BUY:
        payable_count = sum(
            1 for slot in state.market.slots
            if state.am_tokens.get(slot.card.company.id) is not player
        )
        if state.deck and player.money >= payable_count:
            cost_hint = f" (pay ${payable_count})" if payable_count else ""
            actions.append(Action(
                f"Draw from deck{cost_hint}",
                state.buy_from_deck,
            ))
        for i, slot in enumerate(state.market.slots):
            if state.am_tokens.get(slot.card.company.id) is not player:
                label = f"Buy: {slot.card.company.name}"
                if slot.coin_value:
                    label += f"  (+${slot.coin_value})"
                actions.append(Action(label, lambda idx=i: state.buy_from_market(idx)))

    elif state.phase == TurnPhase.PLAY:
        # Group hand cards by company (order of first appearance)
        groups: dict[str, list[int]] = defaultdict(list)
        for i, card in enumerate(player.hand):
            groups[card.company.id].append(i)

        invest_actions: list[Action] = []
        trade_actions:  list[Action] = []

        for company_id, indices in groups.items():
            company   = player.hand[indices[0]].company
            count     = len(indices)
            first_idx = indices[0]
            label     = f"{company.name} ({count})" if count > 1 else company.name

            invest_actions.append(Action(
                f"Invest: {label}",
                lambda idx=first_idx: state.play_as_investment(idx),
            ))

            if company_id != state.last_market_buy_company_id:
                trade_actions.append(Action(
                    f"Trade: {label}",
                    lambda idx=first_idx: state.play_to_market(idx),
                ))

        # All invests first, then all trades
        actions = invest_actions + trade_actions

    return actions


# ──────────────────────────────────────────────────────────────────
# VIEW STATE
# ──────────────────────────────────────────────────────────────────

HISTORY_VISIBLE = 18   # lines shown at once in the History panel


@dataclass
class ViewState:
    panel_index:    int = 0
    menu_cursor:    int = 0   # cursor in the player action menu
    session_cursor: int = 0   # cursor in the game session menu
    history_scroll: int = 0   # index of the first visible history line

    def panel_count(self, num_players: int) -> int:
        return 3 + num_players   # Session | History | Market | Players…

    def scroll_history(self, direction: int, total_lines: int) -> None:
        """history_scroll is an offset from the bottom (0 = show newest).
        UP key increases it (older entries); DOWN key decreases it (newer).
        """
        max_scroll = max(0, total_lines - HISTORY_VISIBLE)
        self.history_scroll = max(0, min(self.history_scroll - direction, max_scroll))

    def navigate(self, direction: int, num_players: int) -> None:
        total = self.panel_count(num_players)
        self.panel_index = (self.panel_index + direction) % total

    def move_cursor(self, direction: int, max_items: int) -> None:
        if max_items > 0:
            self.menu_cursor = max(0, min(self.menu_cursor + direction, max_items - 1))

    def move_session_cursor(self, direction: int) -> None:
        self.session_cursor = (self.session_cursor + direction) % len(_SESSION_OPTIONS)

    def reset_action_cursor(self) -> None:
        self.menu_cursor = 0


# ──────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ──────────────────────────────────────────────────────────────────

def _co_style(color: str) -> str:
    return COMPANY_COLOR.get(color.lower(), "white")


def _nav_bar(current: int, total: int) -> Text:
    t = Text(justify="center")
    t.append("◀  ", style="bold cyan")
    t.append(f"{current} / {total}", style="bold white")
    t.append("  ▶", style="bold cyan")
    return t


def _grouped_card_lines(cards: list[Card]) -> Text:
    """Render a list of cards grouped by company: 'Flamingo Soft (3)'."""
    counts: dict[str, int] = defaultdict(int)
    order:  list[Card]     = []
    seen:   set[str]       = set()
    for card in cards:
        counts[card.company.id] += 1
        if card.company.id not in seen:
            order.append(card)
            seen.add(card.company.id)

    t = Text()
    for card in order:
        style = _co_style(card.company.color)
        n = counts[card.company.id]
        label = f"{card.company.name} ({n})" if n > 1 else card.company.name
        t.append(f"  {label}\n", style=style)
    return t


# ──────────────────────────────────────────────────────────────────
# PANEL 0 — GAME SESSION
# ──────────────────────────────────────────────────────────────────

def render_game_session(state: GameState, view: ViewState) -> Panel:
    n    = view.panel_count(len(state.players))
    meta = state.meta
    t    = Text()

    # Title line: name left, version right
    name_str = meta.get("name", "StartUps")
    ver_str  = f"v{meta.get('version', '?')}"
    inner    = PANEL_WIDTH - 4
    pad      = max(1, inner - len(name_str) - len(ver_str))
    t.append(name_str, style="bold magenta")
    t.append(" " * pad)
    t.append(ver_str + "\n", style="dim")
    t.append("\n")

    t.append("Players:       ", style="dim")
    t.append(f"{len(state.players)}\n")
    t.append("Current Turn:  ", style="dim")
    t.append(f"{state.current_player.name}\n", style="bold white")
    t.append("Phase:         ", style="dim")
    t.append(f"{state.phase.name}\n", style="yellow")
    t.append("Deck:          ", style="dim")
    t.append(f"{len(state.deck)} cards\n")
    t.append("Market:        ", style="dim")
    t.append(f"{len(state.market)} open\n")
    t.append("\n")
    t.append(_SEP + "\n", style="dim")
    t.append("\n")

    for i, opt in enumerate(_SESSION_OPTIONS):
        if i == view.session_cursor:
            t.append(f"  ▶ {opt}\n", style="bold yellow")
        else:
            t.append(f"    {opt}\n", style="white")
    t.append("\n")
    t.append("↑↓ select   ↵ confirm\n", style="dim italic")

    return Panel(
        t,
        title=_nav_bar(1, n),
        title_align="center",
        subtitle="[dim]Game Session[/dim]",
        box=rbox.DOUBLE,
        border_style="cyan",
        width=PANEL_WIDTH,
        padding=(0, 1),
    )


# ──────────────────────────────────────────────────────────────────
# PANEL 1 — HISTORY
# ──────────────────────────────────────────────────────────────────

def render_history(state: GameState, view: ViewState) -> Panel:
    n       = view.panel_count(len(state.players))
    lines   = state.history
    total   = len(lines)
    start   = view.history_scroll
    end     = min(start + HISTORY_VISIBLE, total)
    visible = lines[start:end]

    # scroll=0 → show the very latest; scroll=N → N lines before the latest
    end     = max(0, total - view.history_scroll)
    start   = max(0, end - HISTORY_VISIBLE)
    visible = lines[start:end]

    t = Text()

    if total == 0:
        t.append("  (no moves yet)\n", style="dim italic")
    else:
        older = start
        if older > 0:
            t.append(f"  ▲ {older} older entries above\n", style="dim")
        for line in visible:
            if line.startswith("───"):
                t.append(f"{line}\n", style="bold cyan")
            elif "Drew from deck" in line:
                t.append(line + "\n", style="white")
            elif "Bought" in line:
                t.append(line + "\n", style="green")
            elif "Invested" in line:
                t.append(line + "\n", style="yellow")
            elif "Traded" in line:
                t.append(line + "\n", style="magenta")
            else:
                t.append(line + "\n", style="white")
        newer = total - end
        if newer > 0:
            t.append(f"  ▼ {newer} newer entries below\n", style="dim")

    t.append("\n")
    t.append("↑↓ scroll\n", style="dim italic")

    return Panel(
        t,
        title=_nav_bar(2, n),
        title_align="center",
        subtitle="[dim]History[/dim]",
        box=rbox.DOUBLE,
        border_style="cyan",
        width=PANEL_WIDTH,
        padding=(0, 1),
    )


# ──────────────────────────────────────────────────────────────────
# PANEL 2 — MARKET
# ──────────────────────────────────────────────────────────────────

def render_market(state: GameState, view: ViewState) -> Panel:
    n = view.panel_count(len(state.players))
    t = Text()

    t.append("Deck: ", style="dim")
    t.append(f"{len(state.deck)} cards remaining\n")
    t.append("\n")

    t.append("Open Trade Cards\n", style="bold")
    t.append(_SEP + "\n", style="dim")
    if state.market.slots:
        for i, slot in enumerate(state.market.slots):
            style = _co_style(slot.card.company.color)
            t.append(f"  {i}: ", style="dim")
            t.append(slot.card.company.name, style=style)
            if slot.coin_value:
                t.append(f"  +${slot.coin_value}", style="yellow bold")
            t.append("\n")
    else:
        t.append("  (empty)\n", style="dim italic")

    t.append("\n")
    t.append("Anti-Monopoly Chips\n", style="bold")
    t.append(_SEP + "\n", style="dim")
    for company in state.companies:
        holder = state.am_tokens.get(company.id)
        style  = _co_style(company.color)
        t.append(f"  {company.name:<27}", style=style)
        if holder:
            t.append(f"→  {holder.name}\n", style="bold white")
        else:
            t.append("→  —\n", style="dim")

    return Panel(
        t,
        title=_nav_bar(3, n),
        title_align="center",
        subtitle="[dim]Market[/dim]",
        box=rbox.DOUBLE,
        border_style="cyan",
        width=PANEL_WIDTH,
        padding=(0, 1),
    )


# ──────────────────────────────────────────────────────────────────
# PANELS 2+ — PLAYERS
# ──────────────────────────────────────────────────────────────────

def render_player(
    state: GameState,
    view: ViewState,
    player_index: int,
    actions: list[Action],
) -> Panel:
    n            = view.panel_count(len(state.players))
    panel_number = 4 + player_index
    player       = state.players[player_index]
    is_current   = player_index == state.current_player_index

    t = Text()

    # Header: name + money (right-aligned)
    inner    = PANEL_WIDTH - 4
    tag      = "  ★ current" if is_current else ""
    left     = player.name + tag
    right    = f"💰 {player.money}"
    # emoji "💰" is 2 display chars but len()=1, so subtract 1 from padding
    pad      = max(1, inner - len(left) - len(right) - 1)
    t.append(player.name, style="bold green" if is_current else "bold white")
    t.append(tag, style="dim green")
    t.append(" " * pad)
    t.append(right + "\n", style="yellow")
    t.append("\n")

    # AM tokens held — separated by |
    held = [c.name for c in state.companies if state.am_tokens.get(c.id) is player]
    if held:
        t.append("AM: ", style="dim")
        t.append(" | ".join(held) + "\n", style="bold yellow")
        t.append("\n")

    # Hand
    if is_current:
        t.append(f"Hand  ({len(player.hand)} cards)\n", style="bold")
        if player.hand:
            t.append_text(_grouped_card_lines(player.hand))
        else:
            t.append("  (empty)\n", style="dim italic")
    else:
        t.append("Hand:  ", style="dim")
        t.append(f"{len(player.hand)} cards  (hidden)\n", style="dim italic")
    t.append("\n")

    # Tableau
    t.append("Investments\n", style="bold")
    if player.tableau:
        t.append_text(_grouped_card_lines(player.tableau))
    else:
        t.append("  (none)\n", style="dim italic")

    # Action menu — only for the current player
    if is_current:
        t.append("\n")
        t.append(_SEP + "\n", style="dim")
        t.append("Actions", style="bold")
        t.append("          ↑↓ select  ↵ go\n", style="dim italic")

        if actions:
            cursor = min(view.menu_cursor, len(actions) - 1)
            for i, action in enumerate(actions):
                if i == cursor:
                    t.append(f"  ▶ {action.label}\n", style="bold yellow")
                else:
                    t.append(f"    {action.label}\n", style="white")
        else:
            t.append("  (no actions available)\n", style="dim italic")

    return Panel(
        t,
        title=_nav_bar(panel_number, n),
        title_align="center",
        subtitle=f"[dim]{player.name}[/dim]",
        box=rbox.DOUBLE,
        border_style="green" if is_current else "cyan",
        width=PANEL_WIDTH,
        padding=(0, 1),
    )


# ──────────────────────────────────────────────────────────────────
# GAME OVER SCREEN
# ──────────────────────────────────────────────────────────────────

def render_game_over(state: GameState, view: ViewState) -> Panel:
    result = state.result
    t = Text()

    t.append("GAME OVER\n", style="bold magenta")
    t.append("\n")

    if result:
        t.append("Company Leaders\n", style="bold")
        t.append(_SEP + "\n", style="dim")
        for cr in result.company_results:
            company     = next(c for c in state.companies if c.name == cr.company_name)
            style       = _co_style(company.color)
            leader_name = cr.leader.name if cr.leader else "—"
            leader_count = cr.card_counts.get(leader_name, 0)
            t.append(f"  {cr.company_name:<28}", style=style)
            t.append(f"{leader_name}  ", style="bold white")
            t.append(f"({leader_count})\n", style="dim")
        t.append("\n")

        t.append("Final Standings\n", style="bold")
        t.append(_SEP + "\n", style="dim")
        for rank, (name, money) in enumerate(result.final_standings, 1):
            trophy = "🏆 " if rank == 1 else "   "
            t.append(
                f"  {rank}. {trophy}{name:<18}",
                style="bold yellow" if rank == 1 else "white",
            )
            t.append(f"${money}\n", style="yellow" if rank == 1 else "white")
        t.append("\n")

    t.append(_SEP + "\n", style="dim")
    for i, opt in enumerate(_OVER_OPTIONS):
        if i == view.menu_cursor:
            t.append(f"  ▶ {opt}\n", style="bold yellow")
        else:
            t.append(f"    {opt}\n", style="white")
    t.append("\n")
    t.append("↑↓ select   ↵ confirm\n", style="dim italic")

    return Panel(
        t,
        title=Text("  ★  StartUps  ★  ", style="bold magenta"),
        title_align="center",
        box=rbox.DOUBLE,
        border_style="magenta",
        width=PANEL_WIDTH,
        padding=(0, 1),
    )


# ──────────────────────────────────────────────────────────────────
# NEW GAME CONFIRM SCREEN
# ──────────────────────────────────────────────────────────────────

def render_new_game_confirm(console: Console, cursor: int) -> None:
    os.system("clear")
    t = Text()
    t.append("Start a new game?\n\n", style="bold")
    t.append("This will end the current session.\n\n", style="dim")
    t.append(_SEP + "\n", style="dim")
    for i, opt in enumerate(_CONFIRM_OPTIONS):
        if i == cursor:
            t.append(f"  ▶ {opt}\n", style="bold yellow")
        else:
            t.append(f"    {opt}\n", style="white")
    t.append("\n")
    t.append("↑↓ select   ↵ confirm   ESC back\n", style="dim italic")
    console.print(Panel(
        t,
        title=Text("  New Game  ", style="bold magenta"),
        box=rbox.DOUBLE,
        border_style="magenta",
        width=PANEL_WIDTH,
        padding=(0, 1),
    ))


# ──────────────────────────────────────────────────────────────────
# SAVE SCREEN  (text-input prompt)
# ──────────────────────────────────────────────────────────────────

def render_save_screen(console: Console, buf: list[str]) -> None:
    os.system("clear")
    t = Text()
    t.append("Enter save name:\n\n", style="bold")
    t.append("  ")
    t.append("".join(buf), style="white")
    t.append("█\n\n", style="bright_white blink")
    t.append(_SEP + "\n", style="dim")
    t.append("↵ confirm   ESC cancel\n", style="dim italic")
    console.print(Panel(
        t,
        title=Text("  Save Game  ", style="bold cyan"),
        box=rbox.DOUBLE,
        border_style="cyan",
        width=PANEL_WIDTH,
        padding=(0, 1),
    ))


# ──────────────────────────────────────────────────────────────────
# LOAD SCREEN  (file-picker list)
# ──────────────────────────────────────────────────────────────────

def render_load_screen(console: Console, saves: list[Path], cursor: int) -> None:
    os.system("clear")
    t = Text()
    if not saves:
        t.append("No save files found.\n", style="dim italic")
    else:
        for i, path in enumerate(saves):
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d  %H:%M")
            stem  = path.stem
            # truncate long names so the date still fits
            if len(stem) > 22:
                stem = stem[:19] + "..."
            if i == cursor:
                t.append(f"  ▶ {stem:<24}  {mtime}\n", style="bold yellow")
            else:
                t.append(f"    {stem:<24}  {mtime}\n", style="white")
    t.append("\n")
    t.append(_SEP + "\n", style="dim")
    t.append("↑↓ select   ↵ load   ESC back\n", style="dim italic")
    console.print(Panel(
        t,
        title=Text("  Load Game  ", style="bold cyan"),
        box=rbox.DOUBLE,
        border_style="cyan",
        width=PANEL_WIDTH,
        padding=(0, 1),
    ))


# ──────────────────────────────────────────────────────────────────
# TOP-LEVEL RENDER
# ──────────────────────────────────────────────────────────────────

def render_screen(
    console: Console,
    state: GameState,
    view: ViewState,
    actions: list[Action],
) -> None:
    os.system("clear")

    if state.game_phase == GamePhase.GAME_OVER:
        console.print(render_game_over(state, view))
        return

    idx = view.panel_index
    if idx == 0:
        panel = render_game_session(state, view)
    elif idx == 1:
        panel = render_history(state, view)
    elif idx == 2:
        panel = render_market(state, view)
    else:
        panel = render_player(state, view, idx - 3, actions)

    console.print(panel)
    console.print("\n  [dim]← → navigate panels[/dim]")


# ──────────────────────────────────────────────────────────────────
# LOBBY SCREEN  (player setup before a game starts)
# ──────────────────────────────────────────────────────────────────

@dataclass
class LobbySlot:
    """One player seat in the lobby — a name and a human/AI flag."""
    name:  str
    is_ai: bool = False


def render_lobby(
    console:       Console,
    slots:         list[LobbySlot],
    cursor:        int,
    editing_index: int | None,
    edit_buf:      list[str],
) -> None:
    os.system("clear")
    t = Text()
    t.append(f"  {MIN_PLAYERS}–{MAX_PLAYERS} players\n\n", style="dim")

    for i, slot in enumerate(slots):
        selected = (cursor == i) and editing_index is None
        editing  = (editing_index == i)
        tag      = "[AI   ]" if slot.is_ai else "[Human]"
        tag_sty  = "bright_blue" if slot.is_ai else "green"

        if editing:
            t.append(f"  ▶ Player {i + 1}:  ", style="bold yellow")
            t.append("".join(edit_buf), style="white")
            t.append("█  ", style="bright_white blink")
            t.append(f"{tag}\n", style=tag_sty)
        elif selected:
            t.append(f"  ▶ Player {i + 1}:  ", style="bold yellow")
            t.append(f"{slot.name:<16}", style="bold white")
            t.append(f"{tag}\n", style=f"bold {tag_sty}")
        else:
            t.append(f"    Player {i + 1}:  ", style="dim")
            t.append(f"{slot.name:<16}", style="white")
            t.append(f"{tag}\n", style=tag_sty)

    t.append("\n")
    t.append(_SEP + "\n", style="dim")

    # Start Game row (always last)
    if cursor == len(slots) and editing_index is None:
        t.append("  ▶ Start Game\n", style="bold green")
    else:
        t.append("    Start Game\n", style="green")

    t.append("\n")
    t.append(_SEP + "\n", style="dim")

    if editing_index is not None:
        t.append("Type name   ↵ confirm   ESC cancel\n", style="dim italic")
    else:
        hints = "↑↓ select   ←→ toggle AI   ↵ edit / start"
        if len(slots) < MAX_PLAYERS:
            hints += "   A add"
        if len(slots) > MIN_PLAYERS:
            hints += "   R remove"
        hints += "   Q quit"
        t.append(hints + "\n", style="dim italic")

    console.print(Panel(
        t,
        title=Text("  StartUps — Player Setup  ", style="bold magenta"),
        box=rbox.DOUBLE,
        border_style="magenta",
        width=PANEL_WIDTH,
        padding=(0, 1),
    ))
