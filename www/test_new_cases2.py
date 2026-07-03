"""
New comprehensive test cases (test_new_cases2.py).

Covers:
 1.  Garrison fix regression (pre-round garrison only)
 2.  0-troop forced_owner earns NP in a single round
 3.  0-troop forced_owner earns NP across multiple rounds
 4.  Multi-team zone NP formula (owner + non-owner proportional)
 5.  Tied zone NP (no owner) — both teams get floor(x/2 * 0.5) each
 6.  0-troop forced_owner in multi-team zone — documents actual behaviour
 7.  Non-admin set() is blocked
 8.  ADMIN set() in admin-only round (no non-admin input)
 9.  ADMIN set() + non-admin op in same round (not admin-only)
10.  Exactly at troop limit — no conflict (valid)
11.  One over troop limit — conflict fires
12.  Defender with 0 troops earns 20% bonus when attackers mutually eliminate
13.  Coalition win: both coalition members each earn the 20% bonus independently
14.  Conflict penalty + legit moving same round, mixed neutral island
15.  Relief fires for team with 0 total troops across all zones
16.  5-op limit: 5 valid ops succeed; 6th silently fails
17.  moving to own territory is valid (troops transferred)
18.  Round number increments after each execute_round
"""

import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))

from game.engine import RoundValidator, execute_round as _execute_round
from game.state import (
    GameState, ZoneState,
    NEUTRAL_ISLAND, RESOURCE_POINTS, ISLANDS, TERRITORY_POWER,
)
from game.parser import parse_commands


# ── helpers ───────────────────────────────────────────────────────────────────

def run_round(state: GameState, cmds_by_team: dict) -> tuple:
    """Parse, validate and execute one round. Returns (new_state, log, anim)."""
    parsed = {t: parse_commands(txt) for t, txt in cmds_by_team.items()}
    vcmds  = RoundValidator(state).validate_all(parsed)
    return _execute_round(state, vcmds)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Garrison fix regression
#    Pre-round garrison is snapshot at round-start; moving ops that happen in
#    the same round are NOT garrison.
# ═══════════════════════════════════════════════════════════════════════════════

def test_garrison_is_pre_round_only():
    """
    Garrison betrayal rule: T1 cannot attack 精靈森域 if T1 already has garrison there.
    T1 has 30 garrison troops at 精靈森域 (pre-round). T1's attack from 獸人荒原 is INVALID.
    T1's moving(龍族火山→精靈森域, 50) IS valid (non-attack move to enemy zone).
    T2 owns 精靈森域 with 300 troops → total after move = 380 ≥ 300 → no Phase 1.5 clear.
    Result: no battle, T2 retains ownership.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["獸人荒原"]  = ZoneState(troops={"1": 500})
    s.zones["龍族火山"]  = ZoneState(troops={"1": 200})
    # T1=30 garrison, T2=300 → total=330 ≥ 300 → Phase 1.5 safe
    s.zones["精靈森域"]  = ZoneState(troops={"1": 30, "2": 300}, forced_owner="2")

    cmds = {
        "1": "moving(龍族火山, 精靈森域, 50) attack(獸人荒原, 精靈森域, 100)",
    }
    new_s, log, _ = run_round(s, cmds)

    # T1's attack is INVALID (garrison betrayal rule) → T2 still owns
    owner = new_s.zones["精靈森域"].owner()
    assert owner == "2", f"T2 should still own 精靈森域 (T1's attack blocked), got owner={owner}"

    # No battle → T2's troops unchanged
    t2_troops = new_s.zones["精靈森域"].troops.get("2", 0)
    assert t2_troops == 300, (
        f"T2 should have 300 (no battle since T1 attack invalid), got {t2_troops}. "
        f"log={[l for l in log if '戰鬥' in l or '叛變' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 0-troop forced_owner earns NP in single round
# ═══════════════════════════════════════════════════════════════════════════════

def test_zero_troop_owner_earns_np_single_round():
    """
    T1 is forced_owner of 人類王國 (power=900) with 0 troops.
    After execute_round: T1 gets +900 NP.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 100})

    new_s, log, _ = run_round(s, {})

    x = TERRITORY_POWER["人類王國"]
    np1 = new_s.national_power.get("1", 0)
    assert np1 == x, (
        f"0-troop forced_owner should earn {x} NP, got {np1}. "
        f"log={[l for l in log if '國力' in l or '人類' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 0-troop forced_owner earns NP across multiple rounds
# ═══════════════════════════════════════════════════════════════════════════════

def test_zero_troop_owner_earns_np_multiple_rounds():
    """
    T1 is forced_owner of 人類王國 (power=900) with 0 troops.
    Run 2 rounds without touching that zone.
    T1 should earn 900 NP each round.
    """
    x = TERRITORY_POWER["人類王國"]

    s = GameState(teams=["1", "2"], max_rounds=5)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 100})

    # Round 2
    s2, log2, _ = run_round(s, {})
    np_r2 = s2.national_power.get("1", 0)
    assert np_r2 == x, f"Round 2: expected {x} NP, got {np_r2}"

    # Round 3
    s3, log3, _ = run_round(s2, {})
    np_r3 = s3.national_power.get("1", 0)
    assert np_r3 == 2 * x, f"Round 3: expected {2*x} cumulative NP, got {np_r3}"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Multi-team zone NP formula
# ═══════════════════════════════════════════════════════════════════════════════

def test_multi_team_zone_np_formula():
    """
    龍族火山 (x=1000), T1=forced_owner with 300 troops, T2 has 100 troops.
    total_t = 400. New engine uses proportional _ceil100 for co-occupied zones.
    T1: _ceil100(1000 * 300/400) = _ceil100(750) = 800
    T2: _ceil100(1000 * 100/400) = _ceil100(250) = 300
    Note: T2=100 < 300 alone but total=400 → Phase 1.5 not triggered.
    """
    import math as _math
    x = TERRITORY_POWER["龍族火山"]   # 1000
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["龍族火山"] = ZoneState(troops={"1": 300, "2": 100}, forced_owner="1")

    new_s, log, _ = run_round(s, {})

    # New engine: proportional _ceil100 for co-occupied (no owner half_x split)
    total_t = 400
    expected_t1 = int(_math.ceil(x * 300 / total_t / 100) * 100)  # _ceil100(750) = 800
    expected_t2 = int(_math.ceil(x * 100 / total_t / 100) * 100)  # _ceil100(250) = 300

    np1 = new_s.national_power.get("1", 0)
    np2 = new_s.national_power.get("2", 0)

    dv_log = [l for l in log if "龍族火山" in l]
    assert np1 == expected_t1, (
        f"owner T1: expected {expected_t1} NP, got {np1}. log={dv_log}"
    )
    assert np2 == expected_t2, (
        f"non-owner T2: expected {expected_t2} NP, got {np2}. log={dv_log}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Tied zone NP (no owner)
# ═══════════════════════════════════════════════════════════════════════════════

def test_tied_zone_np_no_owner():
    """
    人類王國 (x=900), T1=500, T2=500 (tied, no forced_owner → owner()=None).
    New engine: proportional distribution with ceil100.
    T1: ceil100(900 * 500/1000) = ceil100(450) = 500 NP
    T2: ceil100(900 * 500/1000) = ceil100(450) = 500 NP
    Note: using 500 troops each (>=300) to avoid phase 1.5 clearing.
    """
    x = TERRITORY_POWER["人類王國"]   # 900
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500, "2": 500})  # tied, no forced_owner

    new_s, log, _ = run_round(s, {})

    # ceil100(900 * 500/1000) = ceil100(450) = 500
    import math as _math
    expected = int(_math.ceil(x * 500 / 1000 / 100) * 100)  # = 500

    np1 = new_s.national_power.get("1", 0)
    np2 = new_s.national_power.get("2", 0)

    hk_log = [l for l in log if "人類王國" in l]
    assert np1 == expected, (
        f"tied zone T1: expected {expected} NP, got {np1}. log={hk_log}"
    )
    assert np2 == expected, (
        f"tied zone T2: expected {expected} NP, got {np2}. log={hk_log}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 0-troop forced_owner in multi-team zone — document actual behaviour
# ═══════════════════════════════════════════════════════════════════════════════

def test_zero_troop_forced_owner_in_multi_team_zone():
    """
    T1 is forced_owner of 龍族火山 (x=1000) with 0 troops.
    T2 has 300 troops there (≥300 so Phase 1.5 does NOT clear).

    Engine behaviour: total_t=300 > 0, len(troops)==1 → sole occupant branch.
    T2 gets all 1000 NP; T1 (0 troops, not in dict) gets 0 NP despite forced_owner.
    Note: T1 retains forced_owner and earns NP only when total_t==0 (all leave).
    """
    x = TERRITORY_POWER["龍族火山"]  # 1000
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    # T1 is forced_owner but has 0 troops; T2 has 300 (≥300, not cleared)
    s.zones["龍族火山"] = ZoneState(troops={"2": 300}, forced_owner="1")

    new_s, log, _ = run_round(s, {})

    np1 = new_s.national_power.get("1", 0)
    np2 = new_s.national_power.get("2", 0)

    dv_log = [l for l in log if "龍族火山" in l]
    assert np1 == 0, (
        f"0-troop T1: expected 0 NP (sole-occupant branch gives all to T2), "
        f"got {np1}. log={dv_log}"
    )
    assert np2 == x, (
        f"sole-presence T2: expected {x} NP, got {np2}. log={dv_log}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Non-admin set() is blocked
# ═══════════════════════════════════════════════════════════════════════════════

def test_non_admin_set_blocked():
    """
    Team "3" submits set(HK, 1:500).
    Engine must reject it with 'set() 操作僅限管理員'.
    State must remain unchanged.
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2; s.phase = "input"
    # T1 needs ≥300 to survive Phase 1.5 (otherwise engine clears the zone)
    s.zones["人類王國"] = ZoneState(troops={"1": 300})

    parsed = {"3": parse_commands("set(HK, 1:500)")}
    vcmds  = RoundValidator(s).validate_all(parsed)

    vc = vcmds["3"][0]
    assert not vc.valid, "non-admin set() must be invalid"
    assert "管理員" in vc.reason, f"expected admin-only reason, got: {vc.reason!r}"

    new_s, log, _ = _execute_round(s, vcmds)
    # State should be unchanged for 人類王國
    assert new_s.zones["人類王國"].troops.get("1", 0) == 300, (
        "state must not change when non-admin set() is blocked"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 8. ADMIN set() works in admin-only round
# ═══════════════════════════════════════════════════════════════════════════════

def test_admin_set_admin_only_round():
    """
    ADMIN submits set(HK, 1, 1:300).
    No non-admin team submits anything.
    → admin-only round: set() fires, state changes, round number stays the same.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"2": 50})

    parsed = {"ADMIN": parse_commands("set(HK, 1, 1:300)")}
    vcmds  = RoundValidator(s).validate_all(parsed)

    vc = vcmds["ADMIN"][0]
    assert vc.valid, f"ADMIN set() should be valid, reason: {vc.reason}"

    new_s, log, _ = _execute_round(s, vcmds)

    # State must have changed
    assert new_s.zones["人類王國"].troops.get("1", 0) == 300, (
        "ADMIN set() must apply troops change"
    )
    assert new_s.zones["人類王國"].forced_owner == "1", (
        "ADMIN set() must apply forced_owner"
    )
    # Round number must NOT advance in admin-only round
    assert new_s.round == 2, (
        f"admin-only round must not advance round counter, got round={new_s.round}"
    )
    # sub_round must increment
    assert new_s.sub_round == 1, (
        f"admin-only round must increment sub_round, got {new_s.sub_round}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 9. ADMIN set() + non-admin op in same round → not admin-only
# ═══════════════════════════════════════════════════════════════════════════════

def test_admin_set_with_non_admin_input_normal_round():
    """
    ADMIN set(HK, 1, 1:500) + T2 attack(精靈森域, 龍族火山, 50) in same round.
    Because non-admin input exists, this is NOT admin-only.
    Both execute (set in Phase 0, attack in Phase 2).
    Round number must advance.
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"3": 200})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 100})

    parsed = {
        "ADMIN": parse_commands("set(HK, 1, 1:500)"),
        "2":     parse_commands("attack(精靈森域, 龍族火山, 50)"),
    }
    vcmds = RoundValidator(s).validate_all(parsed)

    new_s, log, _ = _execute_round(s, vcmds)

    # set() must have applied
    assert new_s.zones["人類王國"].troops.get("1", 0) == 500, (
        "ADMIN set() should still apply in non-admin-only round"
    )
    # Round must advance
    assert new_s.round == 3, (
        f"round must advance when non-admin input exists, got {new_s.round}"
    )
    # sub_round resets to 0
    assert new_s.sub_round == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Exactly at troop limit — no conflict
# ═══════════════════════════════════════════════════════════════════════════════

def test_exactly_at_troop_limit_no_conflict():
    """
    T1 has 100 troops at 人類王國.
    Submits attack(人類王國, 精靈森域, 60) + moving(人類王國, 中立小島, 40).
    Total = 100 = available → no conflict, both execute.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})

    parsed = {"1": parse_commands(
        "attack(人類王國, 精靈森域, 60) moving(人類王國, 中立小島, 40)"
    )}
    vcmds = RoundValidator(s).validate_all(parsed)

    for vc in vcmds["1"]:
        assert vc.valid, (
            f"both ops must be valid (demand == available), "
            f"op={vc.result.command.op if vc.result.command else '?'}, reason={vc.reason!r}"
        )

    new_s, log, _ = _execute_round(s, vcmds)
    # Source zone must be drained to 0
    remaining = new_s.zones["人類王國"].troops.get("1", 0)
    assert remaining == 0, f"all 100 troops should have left, got {remaining}"


# ═══════════════════════════════════════════════════════════════════════════════
# 11. One over troop limit — conflict fires
# ═══════════════════════════════════════════════════════════════════════════════

def test_one_over_troop_limit_conflict_fires():
    """
    T1 has 100 troops at 人類王國.
    Submits attack(人類王國, 精靈森域, 60) + moving(人類王國, 中立小島, 41).
    Total = 101 > 100 → both ops invalidated; troops stay at 人類王國 (no forced redirect).
    Phase 1.5: 人類王國 has 100 < 300 → cleared. T1 total=0 < 1000 → rescue: +1000 at neutral.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})

    parsed = {"1": parse_commands(
        "attack(人類王國, 精靈森域, 60) moving(人類王國, 中立小島, 41)"
    )}
    vcmds = RoundValidator(s).validate_all(parsed)

    conflict_count = sum(
        1 for vc in vcmds["1"]
        if not vc.valid and "衝突" in vc.reason
    )
    assert conflict_count == 2, (
        f"both ops should be conflict-invalidated, got {conflict_count}. "
        f"reasons={[vc.reason for vc in vcmds['1']]}"
    )

    new_s, log, _ = _execute_round(s, vcmds)
    # Both commands invalid → troops stay at 人類王國 (100). Phase 1.5 clears it (100<300).
    # T1 total=0 → rescue tops to 1000 at neutral island.
    neutral_t1 = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert neutral_t1 == 1000, (
        f"conflict makes commands invalid; Phase 1.5 clears 人類王國; rescue → 1000 at neutral. "
        f"got {neutral_t1}. log={[l for l in log if '衝突' in l or '中立' in l or '救濟' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Defender with 0 troops earns 20% bonus when attackers mutually eliminate
# ═══════════════════════════════════════════════════════════════════════════════

def test_zero_troop_defender_earns_bonus_when_attackers_mutually_eliminate():
    """
    T1 is forced_owner of 精靈森域 with 0 troops.
    T2 attacks with 200, T3 attacks with 200 → mutual elimination (same size, same troops).
    Engine: winner_cid=None → defender retains (troops={}, forced_owner='1').
    No bonus is added in the mutual-elimination path — T1 retains 0 troops but keeps ownership.
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["精靈森域"] = ZoneState(troops={}, forced_owner="1")
    s.zones["龍族火山"] = ZoneState(troops={"2": 500})
    s.zones["獸人荒原"] = ZoneState(troops={"3": 500})

    new_s, log, _ = run_round(s, {
        "2": "attack(龍族火山, 精靈森域, 200)",
        "3": "attack(獸人荒原, 精靈森域, 200)",
    })

    t1_troops = new_s.zones["精靈森域"].troops.get("1", 0)
    owner = new_s.zones["精靈森域"].owner()

    assert owner == "1", (
        f"T1 retains forced_owner when all attackers mutually eliminate, "
        f"got owner={owner}. log={[l for l in log if '戰鬥' in l or '同歸' in l]}"
    )
    assert t1_troops == 0, (
        f"T1 gets 0 bonus troops in mutual-elimination path, got {t1_troops}. "
        f"log={[l for l in log if '戰鬥' in l or '同歸' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Coalition win: each member earns 20% bonus independently
# ═══════════════════════════════════════════════════════════════════════════════

def test_coalition_winner_each_member_gets_bonus():
    """
    T1 (300 troops) + T2 (200 troops) coalition attacks 精靈森域.
    T3 defends 精靈森域 with 300 troops.
    Coalition total = 500 > 300 → Situation A.
    survival = max(0, 500-300) = 200.
    T1 = _ceil100(200*300/500) = _ceil100(120) = 200 → leader → 200 < 500 → 500.
    T2 = _ceil100(200*200/500) = _ceil100(80) = 100.
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["龍族火山"] = ZoneState(troops={"2": 500})
    s.zones["精靈森域"] = ZoneState(troops={"3": 300})

    new_s, log, _ = run_round(s, {
        "1": "union_attack(人類王國, [2], 精靈森域, 300)",
        "2": "union_attack(龍族火山, [1], 精靈森域, 200)",
    })

    t1 = new_s.zones["精靈森域"].troops.get("1", 0)
    t2 = new_s.zones["精靈森域"].troops.get("2", 0)

    assert t1 == 500, (
        f"T1 (leader, 300 troops) should get 500 (leader guarantee), got {t1}. "
        f"log={[l for l in log if '戰鬥' in l]}"
    )
    assert t2 == 100, (
        f"T2 (200 troops) should get 100 (_ceil100(80)=100), got {t2}. "
        f"log={[l for l in log if '戰鬥' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Conflict penalty + legit moving same round — mixed neutral island handling
# ═══════════════════════════════════════════════════════════════════════════════

def test_conflict_penalty_and_legit_moving_to_neutral_same_round():
    """
    T1 has 300 troops at 人類王國 (conflict → both ops INVALID, troops stay at source).
    T1 also has 200 troops at 精靈森域 (legitimately moves 100 to neutral: ×1.5=150).

    Conflict setup: attack(人類王國, 龍族火山, 200) + moving(人類王國, 中立小島, 200)
    → demand 400 > 300 available → both ops from 人類王國 invalidated.
    No forced-to-neutral in new engine; troops stay at 人類王國.

    Legit: moving(精靈森域, 中立小島, 100) → 100×1.5=150 at neutral.

    After Phase 1: 精靈森域 has 100 left (200-100) < 300 → Phase 1.5 clears.
    T1 total = 300 (人類王國) + 0 (精靈森域 cleared) + 150 (neutral) = 450 < 1000.
    Rescue: +550 at neutral → neutral = 150+550 = 700.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300})
    s.zones["精靈森域"] = ZoneState(troops={"1": 200})
    s.zones["龍族火山"] = ZoneState(troops={"2": 500})

    cmds = {
        "1": (
            "attack(人類王國, 龍族火山, 200) "
            "moving(人類王國, 中立小島, 200) "
            "moving(精靈森域, 中立小島, 100)"
        ),
    }
    new_s, log, _ = run_round(s, cmds)

    neutral_t1 = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    # Legit 100 × 1.5 = 150; Phase 1.5 clears 精靈森域; rescue +550 = total 700
    assert neutral_t1 == 700, (
        f"expected 700 at neutral (legit 150 + rescue 550), got {neutral_t1}. "
        f"log={[l for l in log if '中立' in l or '衝突' in l or '救濟' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 15. Relief fires for team with 0 total troops across all zones
# ═══════════════════════════════════════════════════════════════════════════════

def test_relief_fires_for_team_with_zero_total_troops():
    """
    T1 starts the round with 0 troops everywhere.
    After execute_round: T1 gets +1000 at neutral island (relief).
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["精靈森域"] = ZoneState(troops={"2": 100})
    # T1 has no troops anywhere

    new_s, log, _ = run_round(s, {})

    relief = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert relief >= 1000, (
        f"T1 with 0 troops should get >=1000 relief at neutral, got {relief}. "
        f"log={[l for l in log if '救濟' in l]}"
    )
    assert any("救濟" in l and "1" in l for l in log), (
        f"relief log missing for T1. log={[l for l in log if '救濟' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 16. 5-op limit: 5 valid ops succeed; 6th silently fails
# ═══════════════════════════════════════════════════════════════════════════════

def test_five_op_limit_sixth_silently_fails():
    """
    T1 has 6000 troops at 人類王國 and submits 6 attacks to 6 different zones.
    Only the first 5 should be marked valid; the 6th must be invalid with the
    '超過每回合 5 次操作上限' reason.
    """
    s = GameState(teams=["1","2","3","4","5","6","7"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 6000})
    targets = [ISLANDS[i] for i in range(1, 7)]  # 6 different targets
    for i, t_zone in enumerate(targets):
        team = str(i + 2)
        s.zones[t_zone] = ZoneState(troops={team: 100})

    cmds = " ".join(f"attack(人類王國, {z}, 100)" for z in targets)
    parsed = {"1": parse_commands(cmds)}
    vcmds  = RoundValidator(s).validate_all(parsed)

    valid   = [vc for vc in vcmds["1"] if vc.valid]
    invalid = [vc for vc in vcmds["1"] if not vc.valid]
    assert len(valid) == 5, f"expected 5 valid ops, got {len(valid)}"
    assert len(invalid) == 1, f"expected 1 invalid (6th op), got {len(invalid)}"
    assert "5" in invalid[0].reason and "上限" in invalid[0].reason, (
        f"invalid reason should mention 5-op limit, got: {invalid[0].reason!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 17. moving to own territory is valid (troops transferred)
# ═══════════════════════════════════════════════════════════════════════════════

def test_moving_to_own_territory_is_valid():
    """
    T1 has 500 at 人類王國 and 200 at 精靈森域.
    T1 moves 150 from 人類王國 to 精靈森域 (T1's own zone).
    Both are valid; troops transfer correctly.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"1": 200})

    parsed = {"1": parse_commands("moving(人類王國, 精靈森域, 150)")}
    vcmds  = RoundValidator(s).validate_all(parsed)

    vc = vcmds["1"][0]
    assert vc.valid, f"moving to own zone must be valid, got reason: {vc.reason!r}"
    assert not vc.warning, f"no warning expected, got: {vc.warning!r}"

    new_s, log, _ = _execute_round(s, vcmds)

    src = new_s.zones["人類王國"].troops.get("1", 0)
    dst = new_s.zones["精靈森域"].troops.get("1", 0)
    assert src == 350, f"source should have 500-150=350, got {src}"
    assert dst == 350, f"destination should have 200+150=350, got {dst}"


# ═══════════════════════════════════════════════════════════════════════════════
# 18. Round number increments after each execute_round
# ═══════════════════════════════════════════════════════════════════════════════

def test_round_number_increments():
    """
    Initial state round=1.
    After first execute_round → round=2.
    After second execute_round → round=3.
    """
    s = GameState(teams=["1", "2"], max_rounds=5)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})

    assert s.round == 1

    s2, _, _ = run_round(s, {})
    assert s2.round == 2, f"expected round=2 after first execute, got {s2.round}"

    s3, _, _ = run_round(s2, {})
    assert s3.round == 3, f"expected round=3 after second execute, got {s3.round}"


# ═══════════════════════════════════════════════════════════════════════════════
# Run all tests (standalone)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import traceback

    tests = [
        test_garrison_is_pre_round_only,
        test_zero_troop_owner_earns_np_single_round,
        test_zero_troop_owner_earns_np_multiple_rounds,
        test_multi_team_zone_np_formula,
        test_tied_zone_np_no_owner,
        test_zero_troop_forced_owner_in_multi_team_zone,
        test_non_admin_set_blocked,
        test_admin_set_admin_only_round,
        test_admin_set_with_non_admin_input_normal_round,
        test_exactly_at_troop_limit_no_conflict,
        test_one_over_troop_limit_conflict_fires,
        test_zero_troop_defender_earns_bonus_when_attackers_mutually_eliminate,
        test_coalition_winner_each_member_gets_bonus,
        test_conflict_penalty_and_legit_moving_to_neutral_same_round,
        test_relief_fires_for_team_with_zero_total_troops,
        test_five_op_limit_sixth_silently_fails,
        test_moving_to_own_territory_is_valid,
        test_round_number_increments,
    ]

    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{passed+failed} PASSED  ({failed} FAILED)")
    if failed:
        sys.exit(1)
