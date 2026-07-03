"""
test_round1.py — First-round test suite (pytest-native).

Required coverage:
  a. Stress test: 10 teams ("1"~"10"), 5 union/union_attack commands per team,
     3 rounds. Verify: no crash, <1s/round, troops non-negative, round increments.
  b. Bug 12 regression: ADMIN set(zone, 0) + same-round move from that zone
     → move must succeed (ADMIN set deferred to Phase 0 after Phase 5).
  c. Bug 11 regression: union(S, P, E, 0) n=0 → invalid.
  d. Bug 10 regression: set() with forced_owner "99" → invalid.
  e. Neutral-island conflict-penalty boundary: conflict troops moved to neutral
     do NOT receive ×1.5; legit troops at neutral DO receive ×1.5.
  f. forced_owner persists cross-round at 0 troops: team wins, troops cleared,
     next round still earns NP.
  g. Gold-island NP formula: proportional to troops present.

Plus additional new tests to reach >= 15 total.
"""

import math
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

import pytest

from game.engine import RoundValidator, execute_round as _execute_round
from game.state import (
    GameState, ZoneState,
    ISLANDS, NEUTRAL_ISLAND, RESOURCE_POINTS, TERRITORY_POWER, ALL_TEAMS,
)
from game.parser import parse_commands


# ── helpers ───────────────────────────────────────────────────────────────────

def run_round(state: GameState, cmds_by_team: dict):
    """Parse, validate and execute one round. Returns (new_state, log, anim)."""
    parsed = {t: parse_commands(txt) for t, txt in cmds_by_team.items()}
    vcmds  = RoundValidator(state).validate_all(parsed)
    return _execute_round(state, vcmds)


def make_10team_state(round_num: int = 1) -> GameState:
    """
    10 teams each owning one of the first 10 islands with 2000 troops each.
    round_num defaults to 1 (union instructions are valid from round 1).
    """
    s = GameState(teams=[str(i) for i in range(1, 11)], max_rounds=5)
    s.round = round_num
    s.phase = "input"
    for i in range(10):
        team = str(i + 1)
        zone = ISLANDS[i]
        s.zones[zone] = ZoneState(troops={team: 2000}, forced_owner=team)
    # Also populate all other zones as empty (GameState __post_init__ handles this)
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# a. Stress test: 10 teams × 5 union/union_attack mixed commands × 3 rounds
# ═══════════════════════════════════════════════════════════════════════════════

def _stress_round_cmds(state: GameState) -> dict[str, str]:
    """
    Build one round of 5 commands per team (union + union_attack mix).
    Strategy:
      - Even teams union_attack their left-neighbour's territory with their right-neighbour as ally.
      - Odd teams union_attack a different target listing 2 allies.
      - Each team also submits a moving command and a union command to fill 5 ops.

    We keep it simple: each team sends 5 union_attack commands to the same
    target (the zone owned by team 10), mutually listing a neighbouring team.
    To avoid the 5-op conflict from same source, we split across:
      - 3 union_attack from home zone with varying troop counts
      - 2 union_attack from home zone (different n) — totalling <= home troops
    Since the constraint is total troop demand from one zone, we send small amounts.
    """
    cmds = {}
    n_teams = 10
    target_zone = ISLANDS[9]  # 套娃族 — always the last island

    for i in range(n_teams):
        team = str(i + 1)
        home = ISLANDS[i]  # team i+1 owns ISLANDS[i]

        # Skip teams that own the target
        if state.zones[target_zone].owner() == team:
            # Pick a different target
            alt_target = ISLANDS[(i + 5) % 9]  # guaranteed different from home
            if state.zones[alt_target].owner() == team:
                alt_target = ISLANDS[(i + 3) % 9]
            target = alt_target
        else:
            target = target_zone

        # Pick two allies: neighbours mod 9 (avoid self and avoid targeting own zone)
        ally1 = str((i + 1) % n_teams + 1)  # next team
        ally2 = str((i + 2) % n_teams + 1)  # team after next
        # Make sure we don't list ourselves
        if ally1 == team:
            ally1 = str((i + 3) % n_teams + 1)
        if ally2 == team or ally2 == ally1:
            ally2 = str((i + 4) % n_teams + 1)

        # Available troops at home
        avail = state.zones[home].troops.get(team, 0)
        if avail < 5:
            # Not enough troops to do anything meaningful; issue moving to neutral
            cmds[team] = f"moving({home}, {NEUTRAL_ISLAND}, 1)"
            continue

        # 5 ops using at most floor(avail * 0.8) total to avoid accidental conflict
        budget = max(5, avail // 5)
        n1 = budget
        n2 = budget
        n3 = budget

        # Op 1: union_attack with ally1 alone (pair)
        # Op 2: union_attack with ally2 alone (pair, different partner)
        # Both attack same target — they will NOT form a coalition because they list different allies
        # Op 3: moving to neutral (always valid)
        # Op 4: union_attack listing [ally1, ally2] — forms a trio IF ally1 and ally2 list back
        # Op 5: another moving to neutral island

        # Check that target is not owned by ally1 or ally2 (union_attack cannot target ally's territory)
        target_owner = state.zones[target].owner()

        # Build 5 valid ops
        op_list = []

        # op1: union_attack(home, [ally1], target, n1)
        if target_owner not in (ally1, team):
            op_list.append(f"union_attack({home}, [{ally1}], {target}, {n1})")
        else:
            op_list.append(f"moving({home}, {NEUTRAL_ISLAND}, {n1})")

        # op2: union_attack(home, [ally2], target, n2)
        # Only if ally2 != team and target not ally2's territory, and different from op1
        if target_owner not in (ally2, team) and ally2 != ally1:
            op_list.append(f"union_attack({home}, [{ally2}], {target}, {n2})")
        else:
            op_list.append(f"moving({home}, {NEUTRAL_ISLAND}, {n2})")

        # op3: moving to neutral
        op_list.append(f"moving({home}, {NEUTRAL_ISLAND}, {n3})")

        # op4: union_attack listing [ally1, ally2]
        if target_owner not in (ally1, ally2, team):
            op_list.append(f"union_attack({home}, [{ally1},{ally2}], {target}, {n1})")
        else:
            op_list.append(f"moving({home}, {NEUTRAL_ISLAND}, {n1})")

        # op5: moving to neutral
        op_list.append(f"moving({home}, {NEUTRAL_ISLAND}, {n2})")

        # Verify total from home does not exceed available
        # (We use budget per op; 5 ops × budget = 5 * budget ≤ avail * 0.8 * 5 / 5 = avail * 0.8)
        # This might still trigger conflict if budget is too large.
        # Safe budget: avail // 6 so 5 * budget <= avail * 5/6 < avail
        safe_budget = max(1, avail // 6)
        ops_safe = []
        for op in op_list:
            # Replace the budget values with safe_budget
            import re
            op_safe = re.sub(r', (\d+)\)$', f', {safe_budget})', op)
            ops_safe.append(op_safe)

        cmds[team] = " ".join(ops_safe)

    return cmds


@pytest.mark.timeout(10)
def test_stress_10teams_5ops_3rounds():
    """
    [Required: a]
    10 teams, each submitting 5 union/union_attack commands per round, 3 rounds.

    Verifications:
    - No exception / crash
    - Each round completes in < 1 second
    - All troop values remain non-negative after each round
    - Round counter increments correctly (starts at 1, ends at 4 after 3 rounds)
    """
    s = make_10team_state(round_num=1)
    timing = []

    expected_round = 1
    for round_idx in range(3):
        assert s.round == expected_round, (
            f"Round {round_idx + 1}: expected round={expected_round}, got {s.round}"
        )

        cmds = _stress_round_cmds(s)

        t_start = time.time()
        s_new, log, anim = run_round(s, cmds)
        t_elapsed = time.time() - t_start

        timing.append(t_elapsed)

        assert t_elapsed < 1.0, (
            f"Round {round_idx + 1} took {t_elapsed:.3f}s (> 1s limit)"
        )

        # No negative troops
        for zone, zs in s_new.zones.items():
            for team, n in zs.troops.items():
                assert n >= 0, (
                    f"Negative troops after round {round_idx + 1}: "
                    f"zone={zone} team={team} n={n}"
                )

        # round incremented (normal round, not admin-only)
        assert s_new.round == expected_round + 1, (
            f"After round {round_idx + 1}: expected round={expected_round + 1}, "
            f"got {s_new.round}"
        )

        s = s_new
        expected_round += 1

    for i, t in enumerate(timing):
        print(f"  Stress round {i + 1}: {t * 1000:.1f}ms")


# ═══════════════════════════════════════════════════════════════════════════════
# b. Bug 12 regression: ADMIN set(zone, 0) + move from that zone same round
#    Move must succeed — ADMIN set is deferred to Phase 0 (after Phase 5)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug12_admin_set_zero_troops_same_round_move_succeeds():
    """
    [Required: b]
    ADMIN submits set(HK, 0) (clear all troops) in the same round that team "1"
    moves 100 troops from HK to neutral island.

    Expected: team "1"'s move succeeds (100 troops leave HK and arrive at neutral).
    The ADMIN set fires AFTER battles (Phase 0 is deferred), so the move reads
    the round-start state (1: 300 troops) and is valid.

    After the round:
    - HK is cleared to 0 (ADMIN set applied last)
    - Neutral island has team 1's 100 troops (×1.5 = 150 after Phase 4)
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 200})

    cmds = {
        "ADMIN": "set(HK, 0)",       # clear HK (forced_owner=0 → clear)
        "1":     "moving(HK, NEU, 100)",
    }
    new_s, log, _ = run_round(s, cmds)

    # Move must have succeeded: neutral island should have team 1's troops.
    # 100 moved → Phase 4: _ceil100(100 * 1.5) = 200. T1 total = 200 (neutral) + 0 (HK cleared) = 200.
    # Phase 4.5 rescue: T1 total 200 < 1000 → topped up to 1000 at neutral.
    neutral_t1 = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert neutral_t1 == 1000, (
        f"Bug 12: team 1's move should succeed before ADMIN set fires. "
        f"After ×1.5 (200) + rescue to 1000. Expected 1000 at neutral, got {neutral_t1}. "
        f"log={[l for l in log if '管理員' in l or 'moving' in l or '中立' in l or '救濟' in l]}"
    )

    # ADMIN set cleared HK (after phase 5)
    hk_total = new_s.zones["人類王國"].total()
    assert hk_total == 0, (
        f"Bug 12: ADMIN set(HK, 0) should clear HK after the round, "
        f"got total={hk_total}. troops={new_s.zones['人類王國'].troops}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# c. Bug 11 regression: union(S, P, E, 0) → invalid (n=0 not allowed)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug11_union_n_zero_is_invalid():
    """
    [Required: c]
    union(S, P, E, 0) — n=0 — should be invalid at parse level because
    _parse_int only returns a value for n >= 1.
    """
    from game.parser import parse_command
    result = parse_command("union(HK, 2, ELF, 0)")
    assert not result.ok, (
        f"Bug 11: union with n=0 should fail parse (n must be >= 1), "
        f"got ok={result.ok}"
    )
    assert result.error, "failed parse must include an error message"


def test_bug11_union_n_zero_engine_also_rejects():
    """
    [Required: c — engine level]
    Even if the parser somehow allows n=0 through, the engine validator
    should also reject union with n <= 0 at the _validate_one level.
    We test the direct validation path by constructing a ParsedCommand with n=0.
    """
    from game.parser import ParsedCommand, CommandResult

    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 300}, forced_owner="2")

    # Manually craft a union command with n=0 (bypassing parser protection)
    fake_cmd = ParsedCommand(
        op="union",
        raw="union(HK, 2, ELF, 0)",
        source="人類王國",
        target="精靈森域",
        nation="2",
        n=0,
    )
    fake_result = CommandResult(raw=fake_cmd.raw, ok=True, command=fake_cmd)

    vcmds = RoundValidator(s).validate_all({"1": [fake_result]})
    vc = vcmds["1"][0]
    assert not vc.valid, (
        f"Bug 11: engine validator must reject union with n=0, got valid={vc.valid}"
    )
    assert "兵力數必須為正整數" in vc.reason or "n" in vc.reason.lower() or "0" in vc.reason, (
        f"Rejection reason should mention n=0 or positive integer, got: {vc.reason!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# d. Bug 10 regression: set() with forced_owner "99" → invalid (unknown team)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug10_set_forced_owner_unknown_team_parse_fails():
    """
    [Required: d — parser level]
    set(HK, 99, 1:500) — team "99" is not in ALL_TEAMS (which is "1".."10").
    The parser should reject this at parse level.
    """
    from game.parser import parse_command
    result = parse_command("set(HK, 99, 1:500)")
    assert not result.ok, (
        f"Bug 10: set() with forced_owner '99' should fail parse, "
        f"got ok={result.ok}"
    )
    assert result.error, "failed parse must include an error message"


def test_bug10_set_forced_owner_unknown_team_engine_rejects():
    """
    [Required: d — engine level]
    Even if parser accepts a set command with nation="99", the engine validator
    must reject it with 'unknown team' error.
    We construct the command manually to test the engine path.
    """
    from game.parser import ParsedCommand, CommandResult

    s = GameState(teams=[str(i) for i in range(1, 11)], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})

    # Manually craft set() with forced_owner="99" — bypasses parser
    fake_cmd = ParsedCommand(
        op="set",
        raw="set(HK, 99, 1:500)",
        source="人類王國",
        nation="99",   # not in ALL_TEAMS
        allies=[("1", 500)],
        n=0,
    )
    fake_result = CommandResult(raw=fake_cmd.raw, ok=True, command=fake_cmd)

    vcmds = RoundValidator(s).validate_all({"ADMIN": [fake_result]})
    vc = vcmds["ADMIN"][0]
    assert not vc.valid, (
        f"Bug 10: engine must reject set() with forced_owner='99', "
        f"got valid={vc.valid}"
    )
    assert "99" in vc.reason or "未知" in vc.reason or "invalid" in vc.reason.lower(), (
        f"Rejection reason should mention '99' or unknown team, got: {vc.reason!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# e. Neutral-island conflict-penalty boundary: penalty troops skip ×1.5
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug_e_conflict_penalty_troops_skip_neutral_1_5x():
    """
    [Required: e — updated for new conflict behavior]
    T1 has 400 at HK. Submits attack(HK, ELF, 300) + attack(HK, DV, 200).
    Both targets are enemy zones. Demand = 500 > 400 → conflict.
    New behavior: both conflicting commands are INVALIDATED (troops stay at HK).
    NO redirect to neutral island.

    T1 also has 200 at GOB (T1-owned). Submits moving(GOB, NEU, 100) — legitimate.

    After round:
    - Conflict commands invalidated: HK stays at 400 (no redirect).
    - Legitimate move: 100 troops move from GOB to neutral → Phase 4: ×1.5 → ceil100(150)=200.
    - GOB remaining = 100 < 300 → Phase 1.5 clears GOB.
    - T1 total after Phase 4: HK=400 + neutral=200 = 600 < 1000 → rescue adds 400 to neutral.
    - Total T1 at neutral = 600.
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"]  = ZoneState(troops={"1": 400}, forced_owner="1")
    s.zones["哥布林族"]  = ZoneState(troops={"1": 200}, forced_owner="1")
    s.zones["精靈森域"]  = ZoneState(troops={"2": 500}, forced_owner="2")
    s.zones["龍族火山"]  = ZoneState(troops={"3": 300}, forced_owner="3")

    cmds = {
        "1": (
            "attack(人類王國, 精靈森域, 300) "
            "attack(人類王國, 龍族火山, 200) "
            "moving(哥布林族, 中立小島, 100)"
        ),
    }
    new_s, log, _ = run_round(s, cmds)

    neutral_t1 = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    # Conflict → troops stay at HK (400). GOB→NEU move: 100 → ×1.5 = 200; GOB cleared (100<300).
    # T1 total = 400+200=600 < 1000 → rescue adds 400 → neutral = 600.
    expected = 600
    assert neutral_t1 == expected, (
        f"Bug e (new): conflict commands invalidated (no redirect); "
        f"legit move 100→×1.5=200, rescue tops to 600. "
        f"Expected {expected} at neutral, got {neutral_t1}. "
        f"log={[l for l in log if '中立' in l or '衝突' in l or '救濟' in l]}"
    )

    # Conflict commands were invalidated — HK troops stay
    hk_t1 = new_s.zones["人類王國"].troops.get("1", 0)
    assert hk_t1 == 400, (
        f"T1's HK troops should stay at 400 (conflict commands invalidated), got {hk_t1}"
    )


def test_bug_e_pure_conflict_no_1_5x_at_all():
    """
    [Required: e — updated for new conflict behavior]
    T1 has 300 at HK. Only conflict ops (demand 400 > 300).
    New behavior: conflicting commands INVALIDATED — troops stay at HK (no redirect).
    T1 total = 300 (all at HK) < 1000 → rescue adds 700 to neutral island.
    T1 at neutral = 700.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 500}, forced_owner="2")
    s.zones["龍族火山"] = ZoneState(troops={"2": 100})

    cmds = {
        "1": "attack(人類王國, 精靈森域, 200) attack(人類王國, 龍族火山, 200)",
    }
    new_s, log, _ = run_round(s, cmds)

    # Conflict commands invalidated → HK stays at 300
    hk_t1 = new_s.zones["人類王國"].troops.get("1", 0)
    assert hk_t1 == 300, (
        f"Bug e: conflicting commands invalidated → HK stays at 300, got {hk_t1}"
    )

    neutral_t1 = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    # Rescue: T1 total = 300 < 1000 → adds 700 to neutral
    assert neutral_t1 == 700, (
        f"Bug e (new): conflict → no redirect; rescue adds 700 to neutral. "
        f"Expected 700 at neutral, got {neutral_t1}. "
        f"log={[l for l in log if '中立' in l or '救濟' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# f. forced_owner persists across rounds at 0 troops → still earns NP
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug_f_forced_owner_zero_troops_cross_round_earns_np():
    """
    [Required: f]
    Round N: T1 wins 龍族火山 (x=1000). After battle T1 has troops there.
    Round N+1: T1 moves all its troops OUT of 龍族火山 (to neutral).
              T1 ends round N+1 with 0 troops at 龍族火山 but forced_owner="1".
    Round N+2: T1 should still earn 1000 NP from 龍族火山 (0-troop 領主 rule).
    """
    x = TERRITORY_POWER["龍族火山"]  # 1000

    # Set up: T1 already owns 龍族火山 with troops
    s = GameState(teams=["1", "2"], max_rounds=5)
    s.round = 2
    s.phase = "input"
    s.zones["龍族火山"] = ZoneState(troops={"1": 300}, forced_owner="1")
    s.zones["人類王國"]  = ZoneState(troops={"2": 200})

    # Round 2: T1 moves all troops out of 龍族火山
    s2, log2, _ = run_round(s, {
        "1": "moving(龍族火山, 中立小島, 300)",
    })

    # After round 2: T1 should have 0 troops at 龍族火山, but forced_owner persists
    assert s2.zones["龍族火山"].total() == 0 or \
           s2.zones["龍族火山"].troops.get("1", 0) == 0, (
        f"T1 should have 0 troops at 龍族火山 after moving them out. "
        f"troops={s2.zones['龍族火山'].troops}"
    )
    assert s2.zones["龍族火山"].forced_owner == "1", (
        f"forced_owner should persist as '1' even at 0 troops. "
        f"forced_owner={s2.zones['龍族火山'].forced_owner}"
    )
    np_after_r2 = s2.national_power.get("1", 0)
    assert np_after_r2 >= x, (
        f"T1 should earn NP in round 2 (owns 龍族火山 with 300 troops), "
        f"got {np_after_r2}"
    )

    # Round 3: nobody touches 龍族火山; T1 has 0 troops there
    np_before_r3 = s2.national_power.get("1", 0)
    s3, log3, _ = run_round(s2, {})

    np_after_r3 = s3.national_power.get("1", 0)
    np_gained_r3 = np_after_r3 - np_before_r3

    # T1 should gain x NP as 0-troop 領主
    assert np_gained_r3 == x, (
        f"Bug f: 0-troop forced_owner should still earn {x} NP in round 3 "
        f"(cross-round persistence). Got NP gain = {np_gained_r3}. "
        f"log={[l for l in log3 if '龍族' in l or '國力' in l]}"
    )

    # Also verify the log mentions 0兵力領主
    assert any("0兵力領主" in l for l in log3), (
        f"Log should mention '0兵力領主' for 0-troop forced_owner. "
        f"log={[l for l in log3 if '龍族' in l or '國力' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# g. Gold-island (金錢島) NP formula: proportional to troops
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug_g_gold_island_np_proportional():
    """
    [Required: g — updated for new formula]
    金錢島: 3000 coconuts split EVENLY among all teams present (ceil to 100).
    T1=600, T2=400 (2 teams present): each gets ceil100(3000/2) = 1500 coconuts.
    (No longer proportional to troops — equal split regardless of troop count.)
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["金錢島"] = ZoneState(troops={"1": 600, "2": 400})
    s.national_power["1"] = 0
    s.national_power["2"] = 0

    new_s, log, _ = run_round(s, {})

    gold_log = [l for l in log if "金錢島" in l]

    # New formula: equal split → each gets 1500 (ceil100(3000/2))
    assert any("1500" in l for l in gold_log), (
        f"Bug g: T1 should gain 1500 coconuts from 金錢島 (equal split). log={gold_log}"
    )
    # Both teams get the same share
    assert len([l for l in gold_log if "1500" in l]) == 2, (
        f"Bug g: Both T1 and T2 should each gain 1500 (equal split). log={gold_log}"
    )


def test_bug_g_gold_island_single_team_gets_all():
    """
    [Required: g — single team, updated for new formula]
    金錢島 with only T1=500. T1 gets ceil100(3000/1) = 3000 coconuts.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["金錢島"] = ZoneState(troops={"1": 500})
    s.national_power["1"] = 0

    new_s, log, _ = run_round(s, {})

    gold_log = [l for l in log if "金錢島" in l]
    assert any("3000" in l for l in gold_log), (
        f"Bug g: sole occupant of 金錢島 should gain 3000 coconuts (ceil100(3000/1)). log={gold_log}"
    )


def test_bug_g_gold_island_locked_round1():
    """
    [Required: g — round 1 locked]
    金錢島 is locked in round 1 (no bonus).
    """
    s = GameState(teams=["1"], max_rounds=3)
    s.round = 1
    s.phase = "input"
    s.zones["金錢島"] = ZoneState(troops={"1": 500})

    new_s, log, _ = run_round(s, {})
    gold_log = [l for l in log if "金錢島" in l]
    assert gold_log == [], (
        f"Bug g: 金錢島 should produce no NP in round 1. log={gold_log}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Additional new tests (beyond the 7 required categories)
# ═══════════════════════════════════════════════════════════════════════════════

def test_union_attack_requires_mutual_listing():
    """
    T1 lists T2 as ally; T2 does NOT list T1 → no valid coalition → both solo.
    Verify effective_allies for T1 is empty (solo).
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 500}, forced_owner="2")
    s.zones["龍族火山"] = ZoneState(troops={"3": 100}, forced_owner="3")

    parsed = {
        "1": parse_commands("union_attack(人類王國, [2], 龍族火山, 100)"),
        "2": parse_commands("union_attack(精靈森域, [3], 龍族火山, 100)"),  # T2 lists T3, not T1
    }
    vcmds = RoundValidator(s).validate_all(parsed)

    t1_vc = vcmds["1"][0]
    assert t1_vc.valid, f"T1 union_attack should be valid: {t1_vc.reason}"
    assert t1_vc.effective_allies == [], (
        f"T1 should have no coalition (T2 didn't list T1). "
        f"effective_allies={t1_vc.effective_allies}"
    )


def test_moving_to_enemy_zone_without_garrison_invalid():
    """
    T1 tries moving(HK, ELF, 100) where T1 has NO troops in ELF (enemy territory).
    This is invalid: moving cannot target enemy territory without troops there.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 300}, forced_owner="2")

    parsed = {"1": parse_commands("moving(人類王國, 精靈森域, 100)")}
    vcmds = RoundValidator(s).validate_all(parsed)

    vc = vcmds["1"][0]
    assert not vc.valid, (
        f"moving to enemy territory (no garrison) should be invalid. "
        f"got valid={vc.valid}, reason={vc.reason!r}"
    )


def test_attack_self_owned_territory_invalid():
    """
    T1 submits attack(HK, HK, 100) — attacking own territory → invalid.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 300})

    parsed = {"1": parse_commands("attack(人類王國, 人類王國, 100)")}
    vcmds = RoundValidator(s).validate_all(parsed)

    vc = vcmds["1"][0]
    assert not vc.valid, (
        f"attack on own territory should be invalid. "
        f"got valid={vc.valid}, reason={vc.reason!r}"
    )


def test_union_self_ally_invalid():
    """
    T1 submits help(HK, ELF, 100, 1) — help targeting self as partner → invalid.
    (Old 4-arg union syntax replaced by help(S, E, n, P); self-help is invalid.)
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 300}, forced_owner="2")

    parsed = {"1": parse_commands("help(人類王國, 精靈森域, 100, 1)")}
    vcmds = RoundValidator(s).validate_all(parsed)

    vc = vcmds["1"][0]
    assert not vc.valid, (
        f"help with self as partner should be invalid. "
        f"got valid={vc.valid}, reason={vc.reason!r}"
    )
    assert "自己" in vc.reason, (
        f"Reason should mention '自己'. reason={vc.reason!r}"
    )


def test_union_attack_self_in_allies_invalid():
    """
    T1 submits union_attack(HK, [1, 2], ELF, 100) — self in allies list → invalid.
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"3": 300}, forced_owner="3")

    parsed = {"1": parse_commands("union_attack(人類王國, [1,2], 精靈森域, 100)")}
    vcmds = RoundValidator(s).validate_all(parsed)

    vc = vcmds["1"][0]
    assert not vc.valid, (
        f"union_attack with self in allies should be invalid. "
        f"got valid={vc.valid}, reason={vc.reason!r}"
    )


def test_attack_round1_resource_point_invalid():
    """
    Round 1: attack on resource point is invalid (not just penalized).
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 1
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")

    for rp in RESOURCE_POINTS:
        parsed = {"1": parse_commands(f"attack(人類王國, {rp}, 100)")}
        vcmds = RoundValidator(s).validate_all(parsed)
        vc = vcmds["1"][0]
        assert not vc.valid, (
            f"attack on {rp} in round 1 must be invalid, "
            f"got valid={vc.valid}, reason={vc.reason!r}"
        )


def test_round_phase_done_after_max_rounds():
    """
    After max_rounds executions, state.phase becomes 'done'.
    """
    s = GameState(teams=["1", "2"], max_rounds=2)
    s.round = 1
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})

    # Execute until done
    s2, _, _ = run_round(s, {})
    assert s2.round == 2 and s2.phase == "input", (
        f"After round 1 of 2: should be round=2 phase=input, "
        f"got round={s2.round} phase={s2.phase}"
    )

    s3, _, _ = run_round(s2, {})
    assert s3.phase == "done", (
        f"After max_rounds=2 executions: phase should be 'done', "
        f"got phase={s3.phase}"
    )


def test_five_op_limit_union_and_attack_mixed():
    """
    Team submits 3 attacks + 2 help requests = 5 valid ops (exactly at limit).
    All 5 should be valid. (Old union(S, P, E, n) replaced by help(S, E, n, P).)
    Note: accept does NOT count towards the 5-op limit.
    """
    s = GameState(teams=["1", "2", "3", "4", "5"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 3000}, forced_owner="1")
    targets = [ISLANDS[i] for i in range(1, 4)]
    for i, z in enumerate(targets):
        s.zones[z] = ZoneState(troops={str(i + 2): 100}, forced_owner=str(i + 2))
    # T5 owns ISLANDS[4], T4 owns ISLANDS[3] — help targets must be allies' territories
    s.zones[ISLANDS[4]] = ZoneState(troops={"5": 200}, forced_owner="5")

    # 3 attacks (100 each) + 2 help commands (100 each) = 600 total from 人類王國
    # (within budget of 3000)
    # help(S, E, n, P): source=人類王國, target=ally's territory, n=100, partner=ally
    cmds = (
        f"attack(人類王國, {targets[0]}, 100) "
        f"attack(人類王國, {targets[1]}, 100) "
        f"attack(人類王國, {targets[2]}, 100) "
        f"help(人類王國, {ISLANDS[4]}, 100, 5) "
        f"help(人類王國, {ISLANDS[3]}, 100, 4)"
    )
    parsed = {"1": parse_commands(cmds)}
    vcmds = RoundValidator(s).validate_all(parsed)

    valid_count = sum(1 for vc in vcmds["1"] if vc.valid)
    assert valid_count == 5, (
        f"3 attacks + 2 help commands should all be valid (exactly 5 ops). "
        f"Got {valid_count} valid. "
        f"Details: {[(vc.result.command.op if vc.result.command else '?', vc.valid, vc.reason) for vc in vcmds['1']]}"
    )


def test_bonus_20pct_floor_rounding():
    """
    New Situation A formula:
      T1 attacks with 300, defender (T2) has 7.
      total_attacker=300 > defender=7 → Situation A (attacker wins).
      survival = max(0, 300 - max(7, 0)) = max(0, 293) = 293.
      _ceil100(293) = 300. Leader (T1) guarantee ≥ 500 → T1 gets 500.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["龍族火山"] = ZoneState(troops={"2": 7})  # defender has 7 troops

    new_s, log, _ = run_round(s, {"1": "attack(人類王國, 龍族火山, 300)"})

    t1 = new_s.zones["龍族火山"].troops.get("1", 0)
    # survival=293 → ceil100=300 < 500 → leader guarantee → 500
    expected = 500
    assert t1 == expected, (
        f"Winner: survival=293→ceil100=300 < 500→leader guarantee=500. "
        f"Expected {expected}, got {t1}"
    )
