"""
Game state for 最終大戰 (WWW).

Territories: 12 islands + neutral island + 3 resource points
Teams: 1-10 (number codes as strings)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import copy

# ── Territory definitions ────────────────────────────────────────────────────

ISLANDS = [
    "人類王國", "精靈森域", "龍族火山", "獸人荒原", "巨人山丘", "侏儒劇場",
    "狐族賭館", "機械王國", "布丁狗族", "河童國", "哥布林族", "套娃族",
]

NEUTRAL_ISLAND = "中立小島"

RESOURCE_POINTS = ["迷霧島", "金錢島", "漩渦"]

ALL_ZONES = ISLANDS + [NEUTRAL_ISLAND] + RESOURCE_POINTS

# National power produced per territory per round (difficulty-based)
TERRITORY_POWER: dict[str, int] = {
    "人類王國":  900,
    "精靈森域":  700,
    "龍族火山": 1000,
    "獸人荒原":  600,
    "巨人山丘":  600,
    "侏儒劇場":  600,
    "狐族賭館":  700,
    "機械王國":  900,
    "布丁狗族": 1000,
    "河童國":   1000,
    "哥布林族":  700,
    "套娃族":    700,
}

# English short code for each zone (for commands and display)
ZONE_CODES: dict[str, str] = {
    "人類王國": "HK",
    "精靈森域": "ELF",
    "龍族火山": "DV",
    "獸人荒原": "ORC",
    "巨人山丘": "GNT",
    "侏儒劇場": "DWF",
    "狐族賭館": "FOX",
    "機械王國": "MK",
    "布丁狗族": "PUD",
    "河童國":   "KPA",
    "哥布林族": "GOB",
    "套娃族":   "DOLL",
    "中立小島": "NEU",
    "迷霧島":   "FOG",
    "金錢島":   "GOLD",
    "漩渦":     "VORT",
}

# Accepted aliases in commands (English codes + abbreviations)
ZONE_ALIASES: dict[str, str] = {
    # English short codes
    "HK":   "人類王國",
    "ELF":  "精靈森域",
    "DV":   "龍族火山",
    "ORC":  "獸人荒原",
    "GNT":  "巨人山丘",
    "DWF":  "侏儒劇場",
    "FOX":  "狐族賭館",
    "MK":   "機械王國",
    "PUD":  "布丁狗族",
    "KPA":  "河童國",
    "GOB":  "哥布林族",
    "DOLL": "套娃族",
    "NEU":  "中立小島",
    "FOG":  "迷霧島",
    "GOLD": "金錢島",
    "VORT": "漩渦",
    # Chinese abbreviations (backward compat)
    "neutral": "中立小島",
    "中立":    "中立小島",
    "迷霧":    "迷霧島",
    "金錢":    "金錢島",
    "漩渦島":  "漩渦",
    "R1":      "迷霧島",
    "R2":      "金錢島",
    "R3":      "漩渦",
}

def resolve_zone(name: str) -> Optional[str]:
    """Return canonical zone name or None if not recognized."""
    name = name.strip()
    if name in ALL_ZONES:
        return name
    # Try case-insensitive match for English codes
    upper = name.upper()
    if upper in ZONE_ALIASES:
        return ZONE_ALIASES[upper]
    return ZONE_ALIASES.get(name)


# ── Team definitions ─────────────────────────────────────────────────────────

ALL_TEAMS = [str(i) for i in range(1, 11)]  # ["1", "2", ..., "10"]


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ZoneState:
    """Troops stationed at a zone, keyed by team number string."""
    troops: dict[str, int] = field(default_factory=dict)
    # Set after a coalition garrison-betrayal win to force the occupier
    # (occupation determined by attack forces only, not garrison n_Ac).
    # Cleared when overwritten by the next battle.
    forced_owner: Optional[str] = None

    def total(self) -> int:
        return sum(self.troops.values())

    def owner(self) -> Optional[str]:
        """Occupying team: forced_owner if set (persists at 0 troops per rule 1), otherwise team with most troops."""
        if self.forced_owner:
            return self.forced_owner
        if not self.troops:
            return None
        by_troops = sorted(self.troops.items(), key=lambda kv: kv[1], reverse=True)
        if len(by_troops) == 1:
            return by_troops[0][0]
        if by_troops[0][1] > by_troops[1][1]:
            return by_troops[0][0]
        return None  # tied

    def copy(self) -> "ZoneState":
        return ZoneState(troops=dict(self.troops), forced_owner=self.forced_owner)


@dataclass
class GameState:
    """Complete game state at a point in time."""
    round: int = 1
    max_rounds: int = 3
    phase: str = "setup"  # "setup" | "input" | "executing" | "done"
    # sub_round > 0 means this is an admin-only intermediate version (e.g. 3.1, 3.2)
    sub_round: int = 0

    teams: list[str] = field(default_factory=lambda: [str(i) for i in range(1, 11)])

    # Zone name → ZoneState
    zones: dict[str, ZoneState] = field(default_factory=dict)

    # Accumulated national power per team
    national_power: dict[str, int] = field(default_factory=dict)

    # Commands submitted this round: team → list of raw command strings
    round_commands: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self):
        for zone in ALL_ZONES:
            if zone not in self.zones:
                self.zones[zone] = ZoneState()
        for team in self.teams:
            if team not in self.national_power:
                self.national_power[team] = 0
            if team not in self.round_commands:
                self.round_commands[team] = []

    def total_troops(self, team: str) -> int:
        return sum(z.troops.get(team, 0) for z in self.zones.values())

    def copy(self) -> "GameState":
        gs = GameState.__new__(GameState)
        gs.round = self.round
        gs.max_rounds = self.max_rounds
        gs.phase = self.phase
        gs.sub_round = self.sub_round
        gs.teams = list(self.teams)
        gs.zones = {k: v.copy() for k, v in self.zones.items()}
        gs.national_power = dict(self.national_power)
        gs.round_commands = {k: list(v) for k, v in self.round_commands.items()}
        return gs

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "max_rounds": self.max_rounds,
            "phase": self.phase,
            "sub_round": self.sub_round,
            "teams": self.teams,
            "zones": {
                k: {
                    "code": ZONE_CODES.get(k, ""),
                    "troops": v.troops,
                    "total": v.total(),
                    "owner": v.owner(),
                    "forced_owner": v.forced_owner,
                }
                for k, v in self.zones.items()
            },
            "national_power": self.national_power,
            "round_commands": self.round_commands,
        }
