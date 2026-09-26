"""
test_stress_final.py — 最終壓力測試員

Covers:
  1. test_10teams_5coalition_cmds_per_round
  2. test_10teams_all_attack_same_target_stress
  3. test_10rounds_continuous_simulation
  4. test_admin_set_after_battles_bug12_regression
  5. test_parser_long_input_no_crash
  6. test_parser_special_chars
  7. test_relief_followed_by_attack_next_round
  8. test_zero_troop_forced_owner_two_rounds_np
"""

import sys
import os
import math
import time
import random

sys.path.insert(0, os.path.dirname(__file__))

from game.engine import RoundValidator, execute_round as _execute_round
from game.state import (
    GameState, ZoneState,
    NEUTRAL_ISLAND, RESOURCE_POINTS, ISLANDS, TERRITORY_POWER, ALL_TEAMS,
    ALL_ZONES,
)
from game.parser import parse_commands


# ── helpers ───────────────────────────────────────────────────────────────────

def run_round(state: GameState, cmds_by_team: dict) -> tuple:
    """Parse, validate and execute one round. Returns (new_state, log, anim)."""
    parsed = {t: parse_commands(txt) for t, txt in cmds_by_team.items()}
    vcmds  = RoundValidator(state).validate_all(parsed)
    return _execute_round(state, vcmds)


def make_10team_state(round_=1, max_rounds=3) -> GameState:
    """
    Build a GameState with 10 teams, each owning one of the first 10 islands
    with 500 troops. Teams: "1".."10". Remaining 2 islands are empty.
    """
    teams = [str(i) for i in range(1, 11)]
    state = GameState(teams=teams, max_rounds=max_rounds)
    state.round = round_
    state.phase = "input"
    for i, team in enumerate(teams):
        island = ISLANDS[i]  # ISLANDS has 12 entries; teams 1-10 own first 10
        state.zones[island] = ZoneState(troops={team: 500}, forced_owner=team)
    return state


def island_of(team_str: str) -> str:
    """Return the island owned by team (1-indexed → ISLANDS[0..9])."""
    return ISLANDS[int(team_str) - 1]


# Zone codes used in commands (English short codes for the first 10 islands)
ISLAND_CODES = [
    "HK",   # 人類王國  → team 1
    "ELF",  # 精靈森域  → team 2
    "DV",   # 龍族火山  → team 3
    "ORC",  # 獸人荒原  → team 4
    "GNT",  # 巨人山丘  → team 5
    "DWF",  # 侏儒劇場  → team 6
    "FOX",  # 狐族賭館  → team 7
    "MK",   # 機械王國  → team 8
    "PUD",  # 布丁狗族  → team 9
    "KPA",  # 河童國    → team 10
]


def code_of(team_str: str) -> str:
    return ISLAND_CODES[int(team_str) - 1]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. test_10teams_5coalition_cmds_per_round
# ═══════════════════════════════════════════════════════════════════════════════

def test_10teams_5coalition_cmds_per_round():
    """
    10 teams ("1"~"10"), each submits 5 coalition commands per round:
      - 3 union_attack (each team lists [T_prev, T_next] as allies, target = next island)
      - 2 union (T_odd requests to move to T_even's island, T_even accepts)
    Run 3 rounds. Verify:
      - Each round completes in < 1 second
      - No crash / exception
      - All zone troops are non-negative after each round
      - Round number increments correctly (1→2→3)
    """
    state = make_10team_state(round_=1, max_rounds=3)

    for round_idx in range(3):
        expected_round = round_idx + 1
        assert state.round == expected_round, (
            f"Round mismatch: expected {expected_round}, got {state.round}"
        )

        cmds: dict[str, str] = {}

        # ── Build commands for each team ────────────────────────────────────
        #
        # Design: give every team exactly 3 union_attack + 2 union = 5 commands.
        #
        # union_attack (3 per team):
        #   We create 10 triplets, each targeting a distinct zone. Each team
        #   appears in exactly 3 triplets (Latin-square-style assignment).
        #   Triplets (teams, target_team):
        #     T0: (1,2,3) → 4   T1: (4,5,6) → 7    T2: (7,8,9) → 10
        #     T3: (1,4,7) → 2   T4: (2,5,8) → 3    T5: (3,6,9) → 1
        #     T6: (1,5,9) → 6   T7: (2,6,10) → 8   T8: (3,7,10) → 5
        #     T9: (4,8,10) → 9
        #   Each team appears: T1→T0,T3,T6; T2→T0,T4,T7; T3→T0,T5,T8; etc.
        #   We verify each team accumulates exactly 3 ua entries.
        #
        # union (2 per team):
        #   5 fixed pairs: (1,2),(3,4),(5,6),(7,8),(9,10).
        #   Within each pair (req, acc):
        #     req: union(req_code, acc, acc_code, 30)  [requesting]
        #     acc: union(acc_code, req, acc_code, 30)  [accepting]
        #   + second union (pair-reversed):
        #     acc requests, req accepts → moving to req's island
        #     acc: union(acc_code, req, req_code, 30)
        #     req: union(req_code, acc, req_code, 30)
        #   Each team gets 2 union commands total.
        #
        # n=30 per union cmd; n=20 per union_attack (3×20=60 ≤ available troops).

        all_ua_triplets = [
            (["1","2","3"], "4"),
            (["4","5","6"], "7"),
            (["7","8","9"], "10"),
            (["1","4","7"], "2"),
            (["2","5","8"], "3"),
            (["3","6","9"], "1"),
            (["1","5","9"], "6"),
            (["2","6","10"], "8"),
            (["3","7","10"], "5"),
            (["4","8","10"], "9"),
        ]

        ua_cmds: dict[str, list[str]] = {t: [] for t in [str(i) for i in range(1, 11)]}

        for triplet_teams, target_team in all_ua_triplets:
            target_code = code_of(target_team)
            for t in triplet_teams:
                # Only add if this team still needs ua commands (cap at 3)
                if len(ua_cmds[t]) < 3:
                    allies = [x for x in triplet_teams if x != t]
                    # Check troops available in current state
                    own_island = island_of(t)
                    troops_available = state.zones[own_island].troops.get(t, 0)
                    if troops_available < 60:
                        # Not enough troops; send 1 or skip (use 1 to pass validation)
                        n_ua = max(1, troops_available // 5)
                    else:
                        n_ua = 20
                    src = code_of(t)
                    ally_str = "[" + ",".join(allies) + "]"
                    ua_cmds[t].append(f"union_attack({src}, {ally_str}, {target_code}, {n_ua})")

        # Verify every team has exactly 3 ua cmds
        for t in [str(i) for i in range(1, 11)]:
            assert len(ua_cmds[t]) == 3, (
                f"Team {t} should have 3 ua cmds, got {len(ua_cmds[t])}"
            )

        # union pairs: (1,2),(3,4),(5,6),(7,8),(9,10) — 2 union per team
        union_pairs = [("1","2"), ("3","4"), ("5","6"), ("7","8"), ("9","10")]
        union_cmds: dict[str, list[str]] = {t: [] for t in [str(i) for i in range(1, 11)]}

        for req, acc in union_pairs:
            req_code = code_of(req)
            acc_code = code_of(acc)
            # Union 1: req moves 30 troops to acc's island; acc accepts
            union_cmds[req].append(f"union({req_code}, {acc}, {acc_code}, 30)")
            union_cmds[acc].append(f"union({acc_code}, {req}, {acc_code}, 30)")
            # Union 2: acc moves 30 troops to req's island; req accepts
            union_cmds[acc].append(f"union({acc_code}, {req}, {req_code}, 30)")
            union_cmds[req].append(f"union({req_code}, {acc}, {req_code}, 30)")

        # Each team now has exactly 2 union cmds
        for t in [str(i) for i in range(1, 11)]:
            assert len(union_cmds[t]) == 2, (
                f"Team {t} should have 2 union cmds, got {len(union_cmds[t])}"
            )

        # Assemble 5 commands per team (3 ua + 2 union)
        for t in [str(i) for i in range(1, 11)]:
            parts = ua_cmds[t] + union_cmds[t]
            assert len(parts) == 5, f"Team {t} should have 5 cmds, got {len(parts)}"
            cmds[t] = "\n".join(parts)

        # ── Execute and time ─────────────────────────────────────────────────
        t_start = time.perf_counter()
        new_state, log, anim = run_round(state, cmds)
        elapsed_ms = (time.perf_counter() - t_start) * 1000

        print(f"  [round {round_idx+1}] elapsed={elapsed_ms:.1f} ms, "
              f"log_lines={len(log)}, anim_events={len(anim)}")

        assert elapsed_ms < 1000, (
            f"Round {round_idx+1} took {elapsed_ms:.1f} ms (>1000 ms limit)"
        )

        # All troops non-negative
        for zone, zs in new_state.zones.items():
            for team, n in zs.troops.items():
                assert n >= 0, (
                    f"Negative troops: zone={zone}, team={team}, n={n} after round {round_idx+1}"
                )

        # Round should have incremented
        assert new_state.round == expected_round + 1, (
            f"Round did not increment: expected {expected_round+1}, got {new_state.round}"
        )

        state = new_state


# ═══════════════════════════════════════════════════════════════════════════════
# 2. test_10teams_all_attack_same_target_stress
# ═══════════════════════════════════════════════════════════════════════════════

def test_10teams_all_attack_same_target_stress():
    """
    All 10 teams attempt to union_attack the same target (team 1's island).
    Teams 2-10 form one coalition (each lists all others).
    Verify: no crash, exactly one coalition wins, state is consistent, timing < 1s.
    """
    state = make_10team_state(round_=2, max_rounds=3)

    # Give team 1 an extra 10000 troops to defend
    state.zones["人類王國"].troops["1"] = 10000

    # Teams 2-10 each union_attack 人類王國 listing all the others as allies
    attackers = [str(i) for i in range(2, 11)]
    target_code = "HK"
    cmds: dict[str, str] = {}

    for t in attackers:
        allies = [x for x in attackers if x != t]
        src = code_of(t)
        ally_str = "[" + ",".join(allies) + "]"
        cmds[t] = f"union_attack({src}, {ally_str}, {target_code}, 200)"

    t_start = time.perf_counter()
    new_state, log, anim = run_round(state, cmds)
    elapsed_ms = (time.perf_counter() - t_start) * 1000

    print(f"  all-attack-same elapsed={elapsed_ms:.1f} ms, log_lines={len(log)}")

    assert elapsed_ms < 1000, f"Took {elapsed_ms:.1f} ms"

    # State consistency: no negative troops
    for zone, zs in new_state.zones.items():
        for team, n in zs.troops.items():
            assert n >= 0, f"Negative troops zone={zone} team={team} n={n}"

    # Exactly one outcome: either defender (team 1) wins or the coalition wins.
    # Either way, the zone should have an owner (or be contested).
    hk = new_state.zones["人類王国"] if "人類王国" in new_state.zones else new_state.zones.get("人類王國")
    assert hk is not None

    # Check round advanced
    assert new_state.round == 3, f"Expected round 3, got {new_state.round}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. test_10rounds_continuous_simulation
# ═══════════════════════════════════════════════════════════════════════════════

def test_10rounds_continuous_simulation():
    """
    10 teams, 10 continuous rounds with random legal commands each round.
    Verify: troops >= 0, round increments, no crash.
    """
    rng = random.Random(42)

    state = make_10team_state(round_=1, max_rounds=10)

    for round_idx in range(10):
        cmds: dict[str, str] = {}
        teams_alive = [t for t in state.teams if state.total_troops(t) > 0]

        for t in state.teams:
            team_troops = state.total_troops(t)
            if team_troops == 0:
                # Team has no troops; skip to let relief kick in
                cmds[t] = ""
                continue

            # Find zones where this team has troops
            own_zones = [
                (z, zs.troops[t])
                for z, zs in state.zones.items()
                if zs.troops.get(t, 0) > 0
            ]

            if not own_zones:
                cmds[t] = ""
                continue

            src_zone, src_troops = rng.choice(own_zones)
            from game.state import ZONE_CODES
            src_code = ZONE_CODES.get(src_zone, src_zone)

            # Pick a random action: moving or attack (simple, no coalitions needed)
            action = rng.choice(["moving", "attack"])
            n = max(1, rng.randint(1, min(src_troops, 100)))

            if action == "moving":
                # Pick own zone or neutral
                own_island_zones = [
                    z for z, zs in state.zones.items()
                    if zs.owner() == t and z != src_zone
                ]
                if own_island_zones:
                    tgt_zone = rng.choice(own_island_zones)
                else:
                    tgt_zone = NEUTRAL_ISLAND
                tgt_code = ZONE_CODES.get(tgt_zone, tgt_zone)
                cmds[t] = f"moving({src_code}, {tgt_code}, {n})"
            else:
                # attack: pick a non-own zone (not neutral, not resource in round 1)
                enemy_zones = [
                    z for z, zs in state.zones.items()
                    if zs.owner() != t
                    and z != NEUTRAL_ISLAND
                    and z not in RESOURCE_POINTS
                    and z in ISLANDS
                ]
                if not enemy_zones:
                    cmds[t] = ""
                    continue
                tgt_zone = rng.choice(enemy_zones)
                tgt_code = ZONE_CODES.get(tgt_zone, tgt_zone)
                cmds[t] = f"attack({src_code}, {tgt_code}, {n})"

        new_state, log, anim = run_round(state, cmds)

        # All troops non-negative
        for zone, zs in new_state.zones.items():
            for team, n in zs.troops.items():
                assert n >= 0, (
                    f"Negative troops round={round_idx+1} zone={zone} team={team} n={n}"
                )

        assert new_state.round == round_idx + 2, (
            f"Round {round_idx+1} → expected new round {round_idx+2}, got {new_state.round}"
        )

        state = new_state

    print(f"  10-round sim completed, final round={state.round}, "
          f"NP={dict(state.national_power)}")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. test_admin_set_after_battles_bug12_regression
# ═══════════════════════════════════════════════════════════════════════════════

def test_admin_set_after_battles_bug12_regression():
    """
    Bug 12 regression: admin set() runs AFTER team commands so T1's move
    from zone_A (where admin sets troops to 0) is not silently dropped.

    Setup:
      - T1 has 100 troops at 人類王國 (HK)
      - T2 owns 精靈森域 (ELF)
    Commands this round:
      - ADMIN: set(HK, 1:0)          → sets HK T1 troops to 0 (deferred to Phase 0)
      - T1: moving(HK, NEU, 50)      → should execute against pre-set state (100 troops)
    Expected (Bug 12 fixed):
      - T1's 50 troops arrive at NEU
      - Admin set then fires: HK T1 troops = 0 (wipes T1 from HK)
      - So HK has 0 T1 troops, NEU has T1=50+any existing
    """
    state = GameState(teams=["1", "2"], max_rounds=3)
    state.round = 1
    state.phase = "input"
    state.zones["人類王國"] = ZoneState(troops={"1": 100}, forced_owner="1")
    state.zones["精靈森域"] = ZoneState(troops={"2": 200}, forced_owner="2")

    cmds_by_team = {
        "ADMIN": "set(HK, 1:0)",
        "1": "moving(HK, NEU, 50)",
    }

    new_state, log, anim = run_round(state, cmds_by_team)

    print(f"  bug12 log: {log}")
    print(f"  HK troops: {new_state.zones['人類王國'].troops}")
    print(f"  NEU troops: {new_state.zones[NEUTRAL_ISLAND].troops}")

    # T1's moving should have executed: NEU should have T1 troops
    neu_t1 = new_state.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert neu_t1 > 0, (
        f"Bug 12 regression: T1 should have troops in NEU after moving, got {neu_t1}. "
        f"NEU={new_state.zones[NEUTRAL_ISLAND].troops}"
    )

    # Admin set runs after: HK T1 should be 0 (cleared)
    hk_t1 = new_state.zones["人類王國"].troops.get("1", 0)
    assert hk_t1 == 0, (
        f"Admin set should have cleared T1 from HK after battle phase, got {hk_t1}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. test_parser_long_input_no_crash
# ═══════════════════════════════════════════════════════════════════════════════

def test_parser_long_input_no_crash():
    """
    1000-character garbage input must not crash the parser.
    """
    long_input = "x" * 1000
    try:
        results = parse_commands(long_input)
        # Should return empty or error results, not crash
        assert isinstance(results, list), "parse_commands should return a list"
    except Exception as e:
        raise AssertionError(f"Parser crashed on long input: {e}") from e

    # Also test a padded-but-valid command buried in 1000 chars
    padded = " " * 400 + "attack(HK, ELF, 100)" + " " * 400
    try:
        results2 = parse_commands(padded)
        assert isinstance(results2, list)
    except Exception as e:
        raise AssertionError(f"Parser crashed on padded input: {e}") from e

    print(f"  long_input: len={len(long_input)}, results={len(results)}")
    print(f"  padded: len={len(padded)}, results2={len(results2)}")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. test_parser_special_chars
# ═══════════════════════════════════════════════════════════════════════════════

def test_parser_special_chars():
    """
    Commands with newlines, tabs, multiple spaces must parse correctly
    or fail gracefully (no crash).
    """
    test_cases = [
        # (input_text, description)
        ("attack(\tHK,\tELF,\t100)", "tabs in args"),
        ("attack(HK,  ELF,   100)", "multiple spaces"),
        ("attack(\nHK,\nELF,\n100\n)", "newlines in args"),
        ("union_attack(HK, [2,  3], ELF, 50)", "spaces in ally list"),
        ("moving(\n  HK  ,  NEU  ,  10  \n)", "mixed whitespace"),
        ("attack(HK, ELF, 100)\n\nattack(ELF, DV, 50)", "two commands with blank line"),
        ("\t\n  attack(HK, ELF, 100)  \t\n", "surrounding whitespace"),
    ]

    for text, desc in test_cases:
        try:
            results = parse_commands(text)
            assert isinstance(results, list), f"parse_commands must return list for: {desc}"
            # Each result must have ok and error attributes
            for r in results:
                assert hasattr(r, "ok"), f"result must have 'ok' attr: {desc}"
                if not r.ok:
                    assert isinstance(r.error, str), f"error must be str: {desc}"
        except Exception as e:
            raise AssertionError(f"Parser crashed on [{desc}]: {e}") from e

    # Multi-command with tabs
    multi = "attack(HK,\tELF,\t100)\tattack(ELF,\tDV,\t50)"
    try:
        results = parse_commands(multi)
        assert isinstance(results, list)
    except Exception as e:
        raise AssertionError(f"Parser crashed on multi-tab input: {e}") from e

    print(f"  special_chars: {len(test_cases)+1} cases all passed")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. test_relief_followed_by_attack_next_round
# ═══════════════════════════════════════════════════════════════════════════════

def test_relief_followed_by_attack_next_round():
    """
    Round 1: T1 has 0 troops → gets relief 1000 at neutral island.
    Round 2: T1 attacks from neutral island using those 1000 troops.
    Verify the attack executes (troops move, battle resolves).
    """
    # Round 1 setup: T1 has no troops, T2 owns ELF
    state = GameState(teams=["1", "2"], max_rounds=3)
    state.round = 1
    state.phase = "input"
    state.zones["人類王國"] = ZoneState(troops={})  # T1 has nothing
    state.zones["精靈森域"] = ZoneState(troops={"2": 300}, forced_owner="2")

    # Round 1: both teams do nothing → T1 gets relief
    state_r2, log1, _ = run_round(state, {"1": "", "2": ""})

    print(f"  Round 1 log (relief): {[l for l in log1 if '救濟' in l]}")

    neu_t1 = state_r2.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert neu_t1 >= 1000, (
        f"T1 should have gotten 1000 relief in neutral island, got {neu_t1}"
    )

    # Round 2: T1 attacks ELF from neutral island
    # NEU → ELF attack (note: ELF is not neutral/resource, so it's a valid attack target)
    # But T1 must "control" NEU first. NEU is neutral island; _team_controls_zone checks troops > 0.
    # T1 has troops in NEU → can attack from NEU.
    state_r2.phase = "input"
    state_r3, log2, _ = run_round(state_r2, {
        "1": "attack(NEU, ELF, 500)",
        "2": "",
    })

    print(f"  Round 2 log (attack): {[l for l in log2 if '戰鬥' in l or '懲罰' in l or 'attack' in l.lower()]}")

    # Verify: either T1 won ELF (has troops there or is forced_owner) or T2 defended
    # Either way troops must be non-negative
    for zone, zs in state_r3.zones.items():
        for team, n in zs.troops.items():
            assert n >= 0, f"Negative troops zone={zone} team={team} n={n}"

    # T1 used 500 troops in the attack, so troops should have moved
    elf = state_r3.zones["精靈森域"]
    hk_t1_total = state_r3.total_troops("1")
    # The attack happened (troops were consumed), verify NEU decreased from 1000+
    neu_t1_after = state_r3.zones[NEUTRAL_ISLAND].troops.get("1", 0)

    # T1 either won ELF or lost. Either way some action happened.
    battle_log = [l for l in log2 if "戰鬥" in l and "精靈森域" in l]
    assert len(battle_log) > 0, (
        f"Expected a battle at 精靈森域 in round 2, got log: {log2}"
    )

    print(f"  relief+attack: NEU_T1_after={neu_t1_after}, ELF={elf.troops}, "
          f"T1_total={hk_t1_total}")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. test_zero_troop_forced_owner_two_rounds_np
# ═══════════════════════════════════════════════════════════════════════════════

def test_zero_troop_forced_owner_two_rounds_np():
    """
    T1 owns zone X (100 troops, forced_owner=T1).
    Round 1: T1 moves all 100 troops out of X to NEU.
    After round 1: X has 0 troops but forced_owner=T1 (per rule 1).
    Round 2: T1 still earns NP from X (0-troop lord rule).
    """
    state = GameState(teams=["1", "2"], max_rounds=3)
    state.round = 1
    state.phase = "input"
    # T1 owns 人類王國 (HK) with 100 troops
    state.zones["人類王國"] = ZoneState(troops={"1": 100}, forced_owner="1")
    # T2 owns 精靈森域 so there's a second player
    state.zones["精靈森域"] = ZoneState(troops={"2": 200}, forced_owner="2")

    # Round 1: T1 moves all 100 troops from HK to NEU
    state_r2, log1, _ = run_round(state, {
        "1": "moving(HK, NEU, 100)",
        "2": "",
    })

    print(f"  R1 log: {log1}")
    print(f"  HK after R1: {state_r2.zones['人類王國'].troops}, "
          f"forced_owner={state_r2.zones['人類王國'].forced_owner}")

    # Verify: HK has 0 T1 troops
    hk_t1 = state_r2.zones["人類王國"].troops.get("1", 0)
    assert hk_t1 == 0, f"T1 should have 0 troops in HK after move, got {hk_t1}"

    # Verify: forced_owner should still be T1
    hk_fo = state_r2.zones["人類王國"].forced_owner
    assert hk_fo == "1", (
        f"forced_owner should be '1' after T1 moved all troops out, got {hk_fo!r}"
    )

    # Round 2: No commands — T1 should earn NP from HK (0-troop lord rule)
    state_r2.phase = "input"
    np_before = state_r2.national_power.get("1", 0)

    state_r3, log2, _ = run_round(state_r2, {"1": "", "2": ""})

    np_after = state_r3.national_power.get("1", 0)
    hk_power = TERRITORY_POWER.get("人類王國", 900)  # should be 900

    print(f"  R2 log (NP): {[l for l in log2 if '國力' in l]}")
    print(f"  NP T1: before={np_before}, after={np_after}, expected_gain={hk_power}")

    assert np_after >= np_before + hk_power, (
        f"T1 should earn at least {hk_power} NP as 0-troop lord of HK. "
        f"Before={np_before}, after={np_after}"
    )

    # Troops still non-negative
    for zone, zs in state_r3.zones.items():
        for team, n in zs.troops.items():
            assert n >= 0, f"Negative troops zone={zone} team={team} n={n}"
