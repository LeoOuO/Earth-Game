"""
New test cases covering areas not yet well tested:

1.  Defender tie-breaking (Rule 1): non-zero defender ties with attacker
2.  Smallest-coalition tie-breaking (Rule 2): solo beats coalition at equal troops
3.  Multi-round state persistence: forced_owner persists; relief troops usable next round
4.  Conflict with union / union_attack (not just moving/attack)
5.  Resource point settlement: 迷霧島 proportional troops, 金錢島 proportional NP, 漩渦 rules
6.  National power multi-team: owner gets half + proportional; non-owner proportional
7.  Moving to neutral island is allowed (no penalty)
8.  Garrison betrayal: losing garrison added to pool → winner gets 20% of it
9.  Zero-troop defender LOSES to anyone with troops
10. Forced_owner persists across two rounds even with no activity
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))

from game.engine import RoundValidator, execute_round as _execute_round
from game.state import GameState, ZoneState, NEUTRAL_ISLAND, RESOURCE_POINTS, ISLANDS
from game.parser import parse_commands


# ── helpers ───────────────────────────────────────────────────────────────────

def run_round(state, cmds_by_team: dict):
    parsed = {t: parse_commands(txt) for t, txt in cmds_by_team.items()}
    vcmds  = RoundValidator(state).validate_all(parsed)
    return _execute_round(state, vcmds)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Defender tie-breaking (Rule 1)
#    Non-zero defender ties with attacker → defender wins
# ═══════════════════════════════════════════════════════════════════════════════

def test_nonzero_defender_wins_tie():
    """
    Team 2 owns 龍族火山 with 300 troops.
    Team 1 attacks with 300 troops (equal total).
    Rule 1: defender wins → team 2 keeps the zone.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"] = ZoneState(troops={"2": 300})

    new_s, log, _ = run_round(s, {"1": "attack(人類王國, 龍族火山, 300)"})
    owner = new_s.zones["龍族火山"].owner()
    assert owner == "2", f"defender should win tie, got owner={owner}"
    # Attacker's 300 troops should be gone from source
    assert new_s.zones["人類王國"].troops.get("1", 0) == 700


def test_nonzero_defender_wins_tie_with_coalition_attacker():
    """
    Team 2 owns zone with 500 troops.
    Teams 1+3 coalition attack with 250+250=500 (equal total).
    Rule 1: defender wins over coalition.
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["精靈森域"] = ZoneState(troops={"3": 1000})
    s.zones["龍族火山"] = ZoneState(troops={"2": 500})

    new_s, log, _ = run_round(s, {
        "1": "union_attack(人類王國, [3], 龍族火山, 250)",
        "3": "union_attack(精靈森域, [1], 龍族火山, 250)",
    })
    owner = new_s.zones["龍族火山"].owner()
    assert owner == "2", f"defender should beat equal coalition, got owner={owner}"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Smallest-coalition tie-breaking (Rule 2)
#    Solo attacker beats coalition at same total troops
# ═══════════════════════════════════════════════════════════════════════════════

def test_solo_beats_coalition_equal_troops():
    """
    No defender (empty zone).
    Solo team 1 sends 300; coalition teams 2+3 send 150+150=300.
    Both totals are 300 → equal.
    Rule 1: no defender. Rule 2: solo (size 1) beats coalition (size 2).
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["精靈森域"] = ZoneState(troops={"2": 1000})
    s.zones["獸人荒原"] = ZoneState(troops={"3": 1000})
    s.zones["龍族火山"] = ZoneState(troops={})  # empty target

    new_s, log, _ = run_round(s, {
        "1": "attack(人類王國, 龍族火山, 300)",
        "2": "union_attack(精靈森域, [3], 龍族火山, 150)",
        "3": "union_attack(獸人荒原, [2], 龍族火山, 150)",
    })
    owner = new_s.zones["龍族火山"].owner()
    assert owner == "1", (
        f"solo attacker should beat equal-troops coalition via Rule 2, got owner={owner}. "
        f"log={[l for l in log if '戰鬥' in l or '同歸' in l]}"
    )


def test_smaller_coalition_beats_larger_coalition_equal_troops():
    """
    No defender.
    2-way coalition (teams 1+2) sends 300+300=600.
    3-way coalition (teams 3+4+5) sends 200+200+200=600.
    Same total; Rule 2: smaller coalition (size 2) wins.
    """
    s = GameState(teams=["1","2","3","4","5"], max_rounds=3)
    s.round = 2; s.phase = "input"
    for i, t in enumerate(["1","2","3","4","5"]):
        s.zones[ISLANDS[i]] = ZoneState(troops={t: 1000})
    s.zones["龍族火山"] = ZoneState(troops={})  # empty target; ISLANDS[2] is 龍族火山
    # Need a different empty target
    target = "獸人荒原"  # ISLANDS[3]
    s.zones[target] = ZoneState(troops={})
    # Rebuild: team 4 and 5 own different zones
    s.zones[ISLANDS[3]] = ZoneState(troops={"4": 1000})
    s.zones[ISLANDS[4]] = ZoneState(troops={"5": 1000})
    # Keep target clear
    s.zones[target].troops = {}

    new_s, log, _ = run_round(s, {
        "1": f"union_attack({ISLANDS[0]}, [2], {target}, 300)",
        "2": f"union_attack({ISLANDS[1]}, [1], {target}, 300)",
        "3": f"union_attack({ISLANDS[2]}, [4,5], {target}, 200)",
        "4": f"union_attack({ISLANDS[3]}, [3,5], {target}, 200)",
        "5": f"union_attack({ISLANDS[4]}, [3,4], {target}, 200)",
    })
    owner = new_s.zones[target].owner()
    assert owner in ("1", "2"), (
        f"2-person coalition (size 2) should beat 3-person coalition (size 3), got {owner}. "
        f"log={[l for l in log if '戰鬥' in l or '同歸' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Multi-round state persistence
# ═══════════════════════════════════════════════════════════════════════════════

def test_forced_owner_persists_across_rounds():
    """
    After team 1 wins a battle, forced_owner is set to "1".
    Next round nobody touches that zone.
    forced_owner should still be "1" in round 3.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["龍族火山"] = ZoneState(troops={"2": 100})

    # Round 1: team 1 attacks and wins
    s2, _, _ = run_round(s, {"1": "attack(人類王國, 龍族火山, 200)"})
    assert s2.zones["龍族火山"].owner() == "1", "team 1 should own zone after winning"
    fo_after_r1 = s2.zones["龍族火山"].forced_owner
    assert fo_after_r1 == "1", f"forced_owner should be '1', got {fo_after_r1}"

    # Round 2: nobody touches 龍族火山
    s3, _, _ = run_round(s2, {})
    assert s3.zones["龍族火山"].forced_owner == "1", (
        f"forced_owner should persist into round 3, got {s3.zones['龍族火山'].forced_owner}"
    )
    assert s3.zones["龍族火山"].owner() == "1"


def test_relief_troops_usable_next_round():
    """
    Team 2 has 0 troops everywhere → gets 1000 relief at neutral island.
    Next round, team 2 can move those troops (they should exist).
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    # Team 2 has no troops anywhere

    # Round 1: empty → team 2 gets relief
    s2, log, _ = run_round(s, {})
    relief = s2.zones[NEUTRAL_ISLAND].troops.get("2", 0)
    assert relief >= 1000, f"team 2 should get >=1000 relief, got {relief}"

    # Round 2: team 2 moves relief troops (neutral → human kingdom, but they own it? No.
    # They can only move to zones they control. Relief is at neutral; they need to attack somewhere.
    # But moving from neutral to neutral is same zone — invalid.
    # Actually they can attack from neutral.  Let's just verify troops exist and they can attack.
    s2.phase = "input"
    neutral_troops = s2.zones[NEUTRAL_ISLAND].troops.get("2", 0)
    assert neutral_troops > 0, "relief troops should be available next round"

    # Try attacking from neutral island (team 2 controls it because they have troops there)
    new_s, log2, _ = run_round(s2, {"2": f"attack({NEUTRAL_ISLAND}, 人類王國, 500)"})
    # Check that team 2's attack consumed neutral troops
    assert new_s.zones[NEUTRAL_ISLAND].troops.get("2", 0) < neutral_troops, (
        "team 2's neutral troops should decrease after attacking"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Conflict penalty for union and union_attack
# ═══════════════════════════════════════════════════════════════════════════════

def test_union_conflict_penalty():
    """
    Team 1 has 300 at 人類王國.
    Team 1 submits union requesting 200 troops + attack 200 troops from same zone = 400 > 300.
    Conflict: all ops from 人類王國 invalidated; 300 troops forced to neutral island.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    # Team 2 agrees to union (accepting role — team 2 owns 精靈森域)
    # Team 1 requests: union(人類王國, 2, 精靈森域, 200)
    # Team 2 accepts: union(人類王國, 1, 精靈森域, 200)

    parsed = {
        "1": parse_commands(
            "union(人類王國, 2, 精靈森域, 200) "
            "attack(人類王國, 龍族火山, 200)"
        ),
        "2": parse_commands("union(人類王國, 1, 精靈森域, 200)"),
    }
    vcmds = RoundValidator(s).validate_all(parsed)

    # Team 1's union and attack should both be invalid due to conflict
    conflict_invalidated = [vc for vc in vcmds["1"] if not vc.valid and "衝突" in vc.reason]
    assert len(conflict_invalidated) >= 1, (
        f"expected at least one conflict-invalidated cmd, got: {[(vc.valid, vc.reason) for vc in vcmds['1']]}"
    )

    new_s, log, _ = _execute_round(s, vcmds)
    # All 300 troops should be at neutral island
    neutral_troops = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert neutral_troops == 300, (
        f"expected 300 at neutral (conflict penalty), got {neutral_troops}. "
        f"log={[l for l in log if '衝突' in l or '中立' in l]}"
    )


def test_union_attack_conflict_penalty():
    """
    Team 1 has 300 at 人類王國.
    Team 1 submits union_attack with 200 + another attack with 200 (same source) = 400 > 300.
    Conflict: all ops from 人類王國 invalidated, 300 troops forced to neutral.
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 500})
    s.zones["獸人荒原"] = ZoneState(troops={"3": 100})

    parsed = {
        "1": parse_commands(
            "union_attack(人類王國, [2], 獸人荒原, 200) "
            "attack(人類王國, 龍族火山, 200)"
        ),
        "2": parse_commands("union_attack(精靈森域, [1], 獸人荒原, 200)"),
        "3": parse_commands(""),
    }
    vcmds = RoundValidator(s).validate_all(parsed)

    conflict_invalidated = [vc for vc in vcmds["1"] if not vc.valid and "衝突" in vc.reason]
    assert len(conflict_invalidated) >= 1, (
        f"union_attack conflict not triggered: {[(vc.valid, vc.reason) for vc in vcmds['1']]}"
    )

    new_s, log, _ = _execute_round(s, vcmds)
    neutral_troops = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert neutral_troops == 300, (
        f"expected 300 at neutral (conflict), got {neutral_troops}. "
        f"log={[l for l in log if '衝突' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Resource point settlement (round >= 2)
# ═══════════════════════════════════════════════════════════════════════════════

def test_foggy_island_troops_proportional():
    """
    迷霧島 with team 1 = 600, team 2 = 400 (total 1000).
    Bonus = 1000 troops distributed proportionally.
    Team 1 gets floor(1000 * 600/1000) = 600.
    Team 2 gets floor(1000 * 400/1000) = 400.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["迷霧島"] = ZoneState(troops={"1": 600, "2": 400})

    new_s, log, _ = run_round(s, {})
    t1 = new_s.zones["迷霧島"].troops.get("1", 0)
    t2 = new_s.zones["迷霧島"].troops.get("2", 0)
    assert t1 == 600 + 600, f"team 1 at 迷霧島 should be 1200, got {t1}"
    assert t2 == 400 + 400, f"team 2 at 迷霧島 should be 800, got {t2}"


def test_gold_island_national_power_proportional():
    """
    金錢島 with team 1 = 750, team 2 = 250 (total 1000).
    Bonus = 1000 NP proportionally.
    Team 1: floor(1000 * 750/1000) = 750 NP.
    Team 2: floor(1000 * 250/1000) = 250 NP.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["金錢島"] = ZoneState(troops={"1": 750, "2": 250})
    s.national_power["1"] = 0
    s.national_power["2"] = 0

    new_s, log, _ = run_round(s, {})
    np1 = new_s.national_power.get("1", 0)
    np2 = new_s.national_power.get("2", 0)
    # NP also includes whatever territory_power is earned this round
    # Isolate: check at least 750 and 250 were added from 金錢島 alone
    gold_log = [l for l in log if "金錢島" in l]
    assert any("+750" in l for l in gold_log), f"expected +750 in 金錢島 log: {gold_log}"
    assert any("+250" in l for l in gold_log), f"expected +250 in 金錢島 log: {gold_log}"


def test_vortex_odd_teams_gives_national_power():
    """
    漩渦 with 1 team only (odd count).
    Odd: distribute 2000 NP proportionally.
    Team 1 is the only team → gets all 2000 NP.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["漩渦"] = ZoneState(troops={"1": 500})
    s.national_power["1"] = 0

    new_s, log, _ = run_round(s, {})
    vortex_log = [l for l in log if "漩渦" in l]
    assert any("2000" in l or "+2000" in l for l in vortex_log), (
        f"expected 2000 NP from vortex (1 team, odd), log={vortex_log}"
    )


def test_vortex_even_teams_gives_troops():
    """
    漩渦 with 2 teams (even, not 4).
    Even (not 4): distribute 2000 troops proportionally.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["漩渦"] = ZoneState(troops={"1": 500, "2": 500})

    before_t1 = s.zones["漩渦"].troops.get("1", 0)
    new_s, log, _ = run_round(s, {})
    after_t1 = new_s.zones["漩渦"].troops.get("1", 0)
    vortex_log = [l for l in log if "漩渦" in l]
    assert after_t1 > before_t1, (
        f"troops at 漩渦 should increase for even teams, got {after_t1} vs {before_t1}. "
        f"log={vortex_log}"
    )
    assert any("偶數" in l for l in vortex_log), f"expected 偶數 in log: {vortex_log}"


def test_vortex_exactly_4_teams_no_output():
    """
    漩渦 with exactly 4 teams → no production.
    """
    s = GameState(teams=["1","2","3","4"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["漩渦"] = ZoneState(troops={"1": 100, "2": 100, "3": 100, "4": 100})
    np_before = {t: s.national_power.get(t, 0) for t in ["1","2","3","4"]}

    new_s, log, _ = run_round(s, {})
    vortex_log = [l for l in log if "漩渦" in l]
    assert any("不產出" in l for l in vortex_log), (
        f"expected '不產出' for 4 teams, log={vortex_log}"
    )


def test_resource_points_locked_round1_no_bonus():
    """Resource points give no bonus in round 1 (all three)."""
    s = GameState(teams=["1"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["迷霧島"] = ZoneState(troops={"1": 500})
    s.zones["金錢島"] = ZoneState(troops={"1": 500})
    s.zones["漩渦"]  = ZoneState(troops={"1": 500})

    new_s, log, _ = run_round(s, {})
    rp_log = [l for l in log if "迷霧島" in l or "金錢島" in l or "漩渦" in l]
    assert len(rp_log) == 0, f"round 1 should have no resource point log, got {rp_log}"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. National power calculation — multi-team zone
# ═══════════════════════════════════════════════════════════════════════════════

def test_national_power_single_team_full_value():
    """Single team on 龍族火山 (power=1000) gets 1000 NP."""
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["龍族火山"] = ZoneState(troops={"1": 500})

    new_s, log, _ = run_round(s, {})
    np1 = new_s.national_power.get("1", 0)
    assert np1 >= 1000, f"team 1 should get >=1000 NP (sole owner of DV), got {np1}"


def test_national_power_multi_team_owner_gets_half_plus_proportional():
    """
    龍族火山 (power=1000), team 1 (owner, forced) has 600, team 2 has 400.
    Total = 1000, half_x = 500.
    team 1 (owner): floor(500 + 500 * 0.6) = floor(500 + 300) = 800
    team 2 (non-owner): floor(500 * 0.4) = floor(200) = 200
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["龍族火山"] = ZoneState(
        troops={"1": 600, "2": 400},
        forced_owner="1"
    )

    new_s, log, _ = run_round(s, {})
    np1 = new_s.national_power.get("1", 0)
    np2 = new_s.national_power.get("2", 0)
    # Only check DV contribution
    dv_log = [l for l in log if "龍族火山" in l]
    assert any("800" in l for l in dv_log) or np1 >= 800, (
        f"owner should get ~800 NP from DV, got np1={np1}. log={dv_log}"
    )
    assert any("200" in l for l in dv_log) or np2 >= 200, (
        f"non-owner should get ~200 NP from DV, got np2={np2}. log={dv_log}"
    )


def test_national_power_tied_zone_no_owner():
    """
    Two teams tied (no owner) on 人類王國 (power=900).
    Each has same troops → owner() returns None.
    With None owner, the half+proportional formula still distributes.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500, "2": 500})  # tied, no owner

    new_s, log, _ = run_round(s, {})
    np1 = new_s.national_power.get("1", 0)
    np2 = new_s.national_power.get("2", 0)
    hk_log = [l for l in log if "人類王國" in l]
    # With no owner, both get floor(450 * 0.5) = 225 each from the NP formula
    # (owner=None means neither gets the bonus half)
    assert np1 > 0 and np2 > 0, (
        f"both teams should get some NP from tied zone, got np1={np1}, np2={np2}. log={hk_log}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Moving to neutral island is allowed (no penalty)
# ═══════════════════════════════════════════════════════════════════════════════

def test_moving_to_neutral_is_allowed():
    """
    Team 1 moves 200 from their own zone to neutral island.
    This is a legitimate moving (not attack), so it should be valid with no warning
    and the troops should arrive at neutral island.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})

    parsed = parse_commands("moving(人類王國, 中立小島, 200)")
    vcmds = RoundValidator(s).validate_all({"1": parsed})
    vc = vcmds["1"][0]
    assert vc.valid, f"moving to neutral should be valid, got reason: {vc.reason}"
    assert not vc.warning, f"moving to neutral should have no warning, got: {vc.warning}"

    new_s, log, _ = _execute_round(s, vcmds)
    neutral = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    source  = new_s.zones["人類王國"].troops.get("1", 0)
    # After moving 200 to neutral, neutral gets ×1.5 = floor(200 * 1.5) = 300
    assert neutral == math.floor(200 * 1.5), (
        f"expected {math.floor(200 * 1.5)} at neutral after ×1.5, got {neutral}"
    )
    assert source == 300, f"expected 300 remaining at source, got {source}"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Garrison betrayal: losing garrison added to pool
# ═══════════════════════════════════════════════════════════════════════════════

def test_garrison_betrayal_losing_increases_bonus():
    """
    Team 2 owns 龍族火山 (200 troops).
    Team 1 has 50 garrison there.
    Team 1 attacks from 人類王國 with 60 → loses (60 < 200).
    Loser pool = attacking 60 + losing garrison 50 = 110.
    Bonus for team 2 = floor(110 * 0.20) = 22.
    Without garrison: floor(60 * 0.20) = 12.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["龍族火山"] = ZoneState(troops={"1": 50, "2": 200})

    new_s, log, _ = run_round(s, {"1": "attack(人類王國, 龍族火山, 60)"})
    t2 = new_s.zones["龍族火山"].troops.get("2", 0)
    expected = 200 + math.floor((60 + 50) * 0.20)  # = 200 + 22 = 222
    without_garrison = 200 + math.floor(60 * 0.20)   # = 200 + 12 = 212
    assert t2 == expected, (
        f"expected {expected} (with garrison in pool), got {t2}. "
        f"Without garrison would be {without_garrison}."
    )


def test_garrison_betrayal_winning_nac_returned():
    """
    Team 1 has 50 garrison at 龍族火山 (owned by team 2 with 100 troops).
    Team 1 attacks with 300 from 人類王國 → wins.
    Winning garrison 50 is returned in full.
    Bonus = floor(100 * 0.20) = 20.
    Team 1 ends with 300 + 20 + 50 = 370 at 龍族火山.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"] = ZoneState(troops={"1": 50, "2": 100})

    new_s, log, _ = run_round(s, {"1": "attack(人類王國, 龍族火山, 300)"})
    t1 = new_s.zones["龍族火山"].troops.get("1", 0)
    expected = 300 + math.floor(100 * 0.20) + 50  # 300 + 20 + 50 = 370
    assert t1 == expected, f"expected {expected} (attack + bonus + returned garrison), got {t1}"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Zero-troop defender LOSES to anyone with troops
# ═══════════════════════════════════════════════════════════════════════════════

def test_zero_troop_defender_loses_to_attacker():
    """
    Team 2 is forced_owner of 龍族火山 but has 0 troops there (moved them away).
    Team 1 attacks with 100 troops → team 1 wins (0 != attacker's positive troops).
    Rule 1 only applies when the defender is tied AT MAX TROOPS; 0 is never tied with 100.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["龍族火山"] = ZoneState(troops={}, forced_owner="2")
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})  # team 2 has troops elsewhere

    new_s, log, _ = run_round(s, {"1": "attack(人類王國, 龍族火山, 100)"})
    owner = new_s.zones["龍族火山"].owner()
    assert owner == "1", (
        f"attacker with troops should beat 0-troop forced_owner, got owner={owner}. "
        f"log={[l for l in log if '戰鬥' in l or '龍族' in l]}"
    )


def test_zero_troop_defender_loses_even_with_defender_advantage():
    """
    Confirm that forced_owner with 0 troops isn't protected by Rule 1 against
    a single attacker — Rule 1 only matters in a TIE at max troops.
    The 0-troop nominal defender is included in the battle but loses.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    # Team 2 owns this via forced_owner but has no troops
    s.zones["龍族火山"] = ZoneState(troops={}, forced_owner="2")

    new_s, log, _ = run_round(s, {"1": "attack(人類王國, 龍族火山, 1)"})
    owner = new_s.zones["龍族火山"].owner()
    assert owner == "1", (
        f"attacker with even 1 troop should beat 0-troop forced_owner. got owner={owner}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Five-op limit per team
# ═══════════════════════════════════════════════════════════════════════════════

def test_five_op_limit_enforced():
    """
    Team submits 6 valid attacks — only first 5 should count; 6th should be invalidated.
    """
    s = GameState(teams=["1","2","3","4","5","6","7"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 5000})
    for i, t in enumerate(["2","3","4","5","6","7"]):
        s.zones[ISLANDS[i+1]] = ZoneState(troops={t: 100})

    # 6 attack commands from zone 人類王國
    cmds = " ".join(
        f"attack(人類王國, {ISLANDS[i+1]}, 100)"
        for i in range(6)
    )
    parsed = parse_commands(cmds)
    vcmds = RoundValidator(s).validate_all({"1": parsed})

    valid_count = sum(1 for vc in vcmds["1"] if vc.valid)
    invalid_count = sum(1 for vc in vcmds["1"] if not vc.valid)
    assert valid_count == 5, f"only 5 ops should be valid, got {valid_count}"
    assert invalid_count == 1, f"6th op should be invalid, got {invalid_count}"


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Round 1 → Round 2: resource points remain locked then unlock
# ═══════════════════════════════════════════════════════════════════════════════

def test_resource_points_unlock_at_round2():
    """
    Round 1: 迷霧島 occupied → no bonus.
    After round 1 → state becomes round 2.
    Round 2: 迷霧島 still occupied → bonus applied.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["迷霧島"] = ZoneState(troops={"1": 1000})
    s.zones["人類王國"] = ZoneState(troops={"1": 500})

    # Round 1 (no resource bonus)
    s2, log1, _ = run_round(s, {})
    assert s2.round == 2
    fog_before = s2.zones["迷霧島"].troops.get("1", 0)
    assert fog_before == 1000, f"no bonus in round 1, fog should stay 1000, got {fog_before}"

    # Round 2 (resource bonus applies)
    s3, log2, _ = run_round(s2, {})
    fog_after = s3.zones["迷霧島"].troops.get("1", 0)
    # 1000 + floor(1000 * 1000/1000) = 1000 + 1000 = 2000
    assert fog_after == 2000, f"expected 2000 at 迷霧島 in round 2, got {fog_after}"


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Neutral island ×1.5 applies to legitimately moved troops
# ═══════════════════════════════════════════════════════════════════════════════

def test_neutral_island_1_5x_legitimate_move():
    """
    Team 1 moves 400 troops to neutral island (legitimate move).
    After round end, they should have floor(400 * 1.5) = 600 at neutral.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})

    new_s, log, _ = run_round(s, {"1": "moving(人類王國, 中立小島, 400)"})
    neutral = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert neutral == math.floor(400 * 1.5), (
        f"expected {math.floor(400 * 1.5)}, got {neutral}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Run all tests
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import traceback
    tests = [
        test_nonzero_defender_wins_tie,
        test_nonzero_defender_wins_tie_with_coalition_attacker,
        test_solo_beats_coalition_equal_troops,
        test_smaller_coalition_beats_larger_coalition_equal_troops,
        test_forced_owner_persists_across_rounds,
        test_relief_troops_usable_next_round,
        test_union_conflict_penalty,
        test_union_attack_conflict_penalty,
        test_foggy_island_troops_proportional,
        test_gold_island_national_power_proportional,
        test_vortex_odd_teams_gives_national_power,
        test_vortex_even_teams_gives_troops,
        test_vortex_exactly_4_teams_no_output,
        test_resource_points_locked_round1_no_bonus,
        test_national_power_single_team_full_value,
        test_national_power_multi_team_owner_gets_half_plus_proportional,
        test_national_power_tied_zone_no_owner,
        test_moving_to_neutral_is_allowed,
        test_garrison_betrayal_losing_increases_bonus,
        test_garrison_betrayal_winning_nac_returned,
        test_zero_troop_defender_loses_to_attacker,
        test_zero_troop_defender_loses_even_with_defender_advantage,
        test_five_op_limit_enforced,
        test_resource_points_unlock_at_round2,
        test_neutral_island_1_5x_legitimate_move,
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


def test_zero_troop_owner_still_earns_national_power():
    """0-troop forced_owner still earns full territory national power."""
    from game.state import TERRITORY_POWER
    zone = "人類王國"
    x = TERRITORY_POWER.get(zone, 700)

    state = GameState(teams=["1", "2"])
    state.zones[zone] = ZoneState(troops={})
    state.zones[zone].forced_owner = "1"
    state.zones["精靈森域"] = ZoneState(troops={"2": 100})

    parsed = {"1": parse_commands(""), "2": parse_commands("")}
    vcmds = RoundValidator(state).validate_all(parsed)
    new_state, log, _ = _execute_round(state, vcmds)

    assert new_state.national_power.get("1", 0) == x, (
        f"expected {x} NP for 0-troop owner, got {new_state.national_power.get('1', 0)}"
    )
    assert any("0兵力領主" in line for line in log), "expected 0兵力領主 in log"
    print("PASS test_zero_troop_owner_still_earns_national_power")
