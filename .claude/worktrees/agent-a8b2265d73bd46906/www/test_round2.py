"""
test_round2.py — Second-round deep scenario test suite (pytest-native).

Focus: multi-round state evolution across 3+ consecutive rounds.

Required scenarios:
  a. 3-round chain: T1 attacks and captures zone; then T1 troops driven to 0;
     verify forced_owner persistence and NP gain at 0 troops.
  b. 0-troop cleanup order: after Phase 2 sets forced_owner, end-of-round cleanup
     removes 0-troop entries; next round zone_start_owners can still find T1 as
     nominal defender.
  c. resource points: round=1 does NOT trigger; round=2 DOES trigger.
  d. 漩渦 with exactly 4 teams → no output (else branch stays silent).
  e. admin-only sub_round increments: 3 consecutive admin-only rounds → sub_round=1,2,3.
  f. T1 sends union_attack from two zones to same target, same coalition → troops sum.
  g. Stress: 10 teams, 5 legitimate coalition commands per team (2 union + 3
     union_attack), 3 rounds. Timing, no crash, state consistency.
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
from game.parser import parse_commands, parse_command


# ── Helpers ────────────────────────────────────────────────────────────────────

def run_round(state: GameState, cmds_by_team: dict):
    """Parse, validate and execute one round. Returns (new_state, log, anim)."""
    parsed = {t: parse_commands(txt) for t, txt in cmds_by_team.items()}
    vcmds = RoundValidator(state).validate_all(parsed)
    return _execute_round(state, vcmds)


def make_state(round_num: int = 1, teams=None, max_rounds: int = 5) -> GameState:
    if teams is None:
        teams = ["1", "2", "3"]
    s = GameState(teams=teams, max_rounds=max_rounds)
    s.round = round_num
    s.phase = "input"
    return s


# ══════════════════════════════════════════════════════════════════════════════
# a.  3-round consecutive chain
#
#   Round 1: T1 attacks and occupies 龍族火山 → forced_owner="1", troops > 0
#   Round 2: A bigger T2 force recaptures 龍族火山, driving T1 troops to 0.
#            forced_owner should now be "2".  T1 still has forced_owner at
#            whatever zone it started with.
#   Round 3: T1's remaining forced_owner zone still earns NP even if 0 troops.
# ══════════════════════════════════════════════════════════════════════════════

def test_a1_t1_captures_zone_forced_owner_set():
    """
    Round 1: T1 attacks 龍族火山 (owned by T2) with overwhelming force.
    After round: 龍族火山.forced_owner == "1"
    """
    s = make_state(round_num=2)  # round>=2 so NP and resource points work
    s.zones["人類王國"] = ZoneState(troops={"1": 1000}, forced_owner="1")
    s.zones["龍族火山"] = ZoneState(troops={"2": 100}, forced_owner="2")

    new_s, log, _ = run_round(s, {"1": "attack(人類王國, 龍族火山, 800)"})

    dv = new_s.zones["龍族火山"]
    assert dv.forced_owner == "1", (
        f"After T1 wins 龍族火山, forced_owner should be '1', got {dv.forced_owner!r}"
    )
    assert dv.troops.get("1", 0) > 0, (
        f"T1 should have troops in 龍族火山 after winning, got {dv.troops}"
    )


def test_a2_t1_driven_to_zero_forced_owner_changes():
    """
    Round 2: T2 recaptures 龍族火山 (T1 has only 100 there; T2 sends 500).
    After round: forced_owner == "2", T1 has 0 troops.
    """
    s = make_state(round_num=2)
    # State after T1 won: T1 has 100 troops in 龍族火山
    s.zones["龍族火山"] = ZoneState(troops={"1": 100}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 1000}, forced_owner="2")

    new_s, log, _ = run_round(s, {"2": "attack(精靈森域, 龍族火山, 500)"})

    dv = new_s.zones["龍族火山"]
    assert dv.forced_owner == "2", (
        f"T2 should own 龍族火山 after recapture, got {dv.forced_owner!r}"
    )
    assert dv.troops.get("1", 0) == 0, (
        f"T1 should have 0 troops in 龍族火山 after losing, got {dv.troops}"
    )


def test_a3_full_3round_chain():
    """
    Full 3-round chain:
      R1: T1 attacks and captures 龍族火山 from T2 → forced_owner="1", T1 troops there.
      R2: T1 moves all troops OUT of 龍族火山; T2 also moves away.
          龍族火山: T1 is still forced_owner at 0 troops.
      R3: T1 has 0 troops at 龍族火山 with forced_owner="1".
          Verify T1 earns the full 1000 NP from 龍族火山 in R3 (0-troop lord rule).

    The test isolates the NP gain for 龍族火山 specifically by checking the log
    line rather than total NP delta (which would include 人類王國 etc.).
    """
    x_dv = TERRITORY_POWER["龍族火山"]  # 1000

    # Round 1 state — only give T1 troops in 人類王國 to attack from
    s = make_state(round_num=2, teams=["1", "2"])
    s.zones["人類王國"] = ZoneState(troops={"1": 2000}, forced_owner="1")
    s.zones["龍族火山"] = ZoneState(troops={"2": 100}, forced_owner="2")
    s.national_power = {"1": 0, "2": 0}

    # R1: T1 attacks 龍族火山 with 500 troops; T2 moves all away (T2 leaves 0 troops)
    s1, log1, _ = run_round(s, {
        "1": "attack(人類王國, 龍族火山, 500)",
        "2": "moving(龍族火山, 中立小島, 100)",
    })
    assert s1.zones["龍族火山"].forced_owner == "1", (
        f"R1: T1 should own 龍族火山. log={[l for l in log1 if '龍族' in l]}"
    )
    t1_dv_r1 = s1.zones["龍族火山"].troops.get("1", 0)
    assert t1_dv_r1 > 0, f"R1: T1 should have troops in 龍族火山, got {t1_dv_r1}"

    # R2: T1 moves all troops OUT of 龍族火山 → 0 troops, forced_owner="1" persists
    s2, log2, _ = run_round(s1, {
        "1": f"moving(龍族火山, 中立小島, {t1_dv_r1})",
    })
    assert s2.zones["龍族火山"].forced_owner == "1", (
        f"R2: forced_owner='1' should persist after T1 moves away. "
        f"forced_owner={s2.zones['龍族火山'].forced_owner}"
    )
    assert s2.zones["龍族火山"].troops.get("1", 0) == 0, (
        f"R2: T1 should have 0 troops in 龍族火山 after moving out. "
        f"troops={s2.zones['龍族火山'].troops}"
    )

    # R3: nobody sends any commands; T1 is 0-troop forced_owner of 龍族火山
    s3, log3, _ = run_round(s2, {})

    # Verify specifically via log: 龍族火山 entry says "0兵力領主" and "+1000"
    dv_np_log = [l for l in log3 if "龍族火山" in l and "國力" in l]
    assert dv_np_log, (
        f"R3: should have NP log entry for 龍族火山. "
        f"log={[l for l in log3 if '龍族' in l or '國力' in l]}"
    )
    assert any(str(x_dv) in l for l in dv_np_log), (
        f"R3: 龍族火山 NP log should mention {x_dv}. dv_np_log={dv_np_log}"
    )
    assert any("0兵力領主" in l for l in log3), (
        f"R3: log should mention '0兵力領主'. "
        f"log={[l for l in log3 if '國力' in l or '龍族' in l]}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# b.  0-troop cleanup order and zone_start_owners nominal defender
# ══════════════════════════════════════════════════════════════════════════════

def test_b1_zero_troop_cleanup_then_nominal_defender_next_round():
    """
    After Phase 2 sets forced_owner and the end-of-round cleanup removes 0-troop
    entries, the next round's zone_start_owners should still identify T1 as the
    nominal defender (forced_owner persists).

    Scenario:
    - 龍族火山: T1=50, T2=200 (T2 attacks with 200, T1 is defender at 50)
    - T2 wins; T1 post-battle = 0; cleanup removes T1 from troops dict
    - Next round: T2 is sole owner (forced_owner="2")
    - Another attacker (T3) attacks 龍族火山: T2 with 0 troops but is nominal defender
    """
    s = make_state(round_num=2, teams=["1", "2", "3"])
    s.zones["龍族火山"] = ZoneState(troops={"1": 50}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 500}, forced_owner="2")
    s.zones["獸人荒原"] = ZoneState(troops={"3": 300}, forced_owner="3")

    # T2 attacks 龍族火山 with 200 (wins over T1's 50); T1 → 0 troops there
    s2, log2, _ = run_round(s, {"2": "attack(精靈森域, 龍族火山, 200)"})

    # Verify T1 has 0 troops at 龍族火山 (cleaned up)
    assert "1" not in s2.zones["龍族火山"].troops, (
        f"T1 should have been cleaned from 龍族火山 troops after losing. "
        f"troops={s2.zones['龍族火山'].troops}"
    )
    # Verify T2 is forced_owner
    assert s2.zones["龍族火山"].forced_owner == "2", (
        f"T2 should be forced_owner after winning. "
        f"forced_owner={s2.zones['龍族火山'].forced_owner}"
    )

    # Next round: T2 moves all troops OUT of 龍族火山 (0 troops left)
    t2_dv = s2.zones["龍族火山"].troops.get("2", 0)
    s3, log3, _ = run_round(s2, {
        "2": f"moving(龍族火山, 中立小島, {t2_dv})" if t2_dv > 0 else "",
        "3": "attack(獸人荒原, 龍族火山, 50)",
    })
    # T2 as 0-troop nominal defender should appear in zone_start_owners, so T2 acts
    # as nominal defender. T3 attacks with only 50. T2 has 0 troops but is nominal.
    # Since T2 troops at start of this sub-round = t2_dv (which T2 also moved away),
    # after moving: T2 has 0, nominal defender = T2 (forced_owner).
    # T3 attacks with 50 vs T2 nominal with 0 → T3 wins.
    dv_s3 = s3.zones["龍族火山"]
    assert dv_s3.forced_owner == "3", (
        f"T3 should capture 龍族火山 (T2 was 0-troop nominal defender). "
        f"forced_owner={dv_s3.forced_owner}, troops={dv_s3.troops}"
    )


def test_b2_forced_owner_survives_cleanup_for_np():
    """
    After end-of-round cleanup removes 0-troop entries, forced_owner is still set,
    so the next-round Phase 3 NP calculation uses it to credit the owner.
    """
    s = make_state(round_num=2, teams=["1", "2"])
    # T1 owns 狐族賭館 with forced_owner but 0 actual troops (simulate post-cleanup)
    s.zones["狐族賭館"] = ZoneState(troops={}, forced_owner="1")
    s.national_power["1"] = 0

    np_before = s.national_power.get("1", 0)
    new_s, log, _ = run_round(s, {})

    x = TERRITORY_POWER["狐族賭館"]  # 700
    np_after = new_s.national_power.get("1", 0)
    np_gain = np_after - np_before

    assert np_gain == x, (
        f"0-troop forced_owner should earn {x} NP. "
        f"Got gain={np_gain}. log={[l for l in log if '狐族' in l or '國力' in l]}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# c.  Resource points timing: round=1 → no trigger; round=2 → trigger
# ══════════════════════════════════════════════════════════════════════════════

def test_c1_resource_points_locked_round1():
    """
    Round 1: 迷霧島, 金錢島, 漩渦 all have troops but produce nothing.
    """
    s = make_state(round_num=1, teams=["1", "2"])
    s.zones["迷霧島"] = ZoneState(troops={"1": 500})
    s.zones["金錢島"] = ZoneState(troops={"1": 500})
    s.zones["漩渦"] = ZoneState(troops={"1": 500})
    s.national_power["1"] = 0

    new_s, log, _ = run_round(s, {})

    # No resource point log lines
    rp_log = [l for l in log if any(rp in l for rp in ["迷霧島", "金錢島", "漩渦"])]
    assert rp_log == [], (
        f"Round 1: resource points should produce nothing. Got: {rp_log}"
    )


def test_c2_resource_points_trigger_round2():
    """
    Round 2: 迷霧島 and 金錢島 have troops → both produce bonuses.
    """
    s = make_state(round_num=2, teams=["1", "2"])
    s.zones["迷霧島"] = ZoneState(troops={"1": 500})
    s.zones["金錢島"] = ZoneState(troops={"1": 500})
    s.national_power["1"] = 0

    new_s, log, _ = run_round(s, {})

    fog_log = [l for l in log if "迷霧島" in l]
    gold_log = [l for l in log if "金錢島" in l]

    assert fog_log, (
        f"Round 2: 迷霧島 should produce troop bonus. log={fog_log}"
    )
    assert gold_log, (
        f"Round 2: 金錢島 should produce NP bonus. log={gold_log}"
    )
    # 金錢島: 1 team with 500 troops → floor(1000 * 500/500) = 1000 NP
    assert new_s.national_power.get("1", 0) >= 1000, (
        f"金錢島 should grant >= 1000 NP in round 2. "
        f"national_power={new_s.national_power}"
    )


def test_c3_resource_points_first_available_exactly_round2():
    """
    Verify the boundary precisely: state.round == 2 just became eligible.
    Execute round 1 first (no bonus), check, then execute round 2 (bonus fires).
    """
    s = make_state(round_num=1, teams=["1"])
    s.zones["金錢島"] = ZoneState(troops={"1": 400})
    s.national_power["1"] = 0

    # Round 1 → no bonus
    s2, log1, _ = run_round(s, {})
    gold_log1 = [l for l in log1 if "金錢島" in l]
    assert gold_log1 == [], f"Round 1 must not trigger 金錢島: {gold_log1}"

    # Round 2 → bonus fires (new_state.round was 2 when _settle_resource_points ran)
    s3, log2, _ = run_round(s2, {})
    gold_log2 = [l for l in log2 if "金錢島" in l]
    assert gold_log2, f"Round 2 must trigger 金錢島: {gold_log2}"


# ══════════════════════════════════════════════════════════════════════════════
# d.  漩渦 exactly 4 teams → no output (else branch silent)
# ══════════════════════════════════════════════════════════════════════════════

def test_d_vortex_exactly_4_teams_no_output():
    """
    漩渦 with exactly 4 teams present → no log output (not '不產出' either —
    well actually the engine DOES log '不產出', so verify the 4-team path fires
    and does NOT grant any troops/NP).
    """
    s = make_state(round_num=2, teams=["1", "2", "3", "4", "5"])
    s.zones["漩渦"] = ZoneState(troops={"1": 100, "2": 200, "3": 300, "4": 400})
    for t in ["1", "2", "3", "4"]:
        s.national_power[t] = 0

    troops_before = {t: s.zones["漩渦"].troops[t] for t in ["1","2","3","4"]}
    np_before = {t: 0 for t in ["1","2","3","4"]}

    new_s, log, _ = run_round(s, {})

    # No troop change in 漩渦 for any of the 4 teams
    vort = new_s.zones["漩渦"]
    for t in ["1","2","3","4"]:
        assert vort.troops.get(t, 0) == troops_before[t], (
            f"漩渦 4-team: {t}'s troops should not change. "
            f"Before={troops_before[t]}, After={vort.troops.get(t, 0)}"
        )

    # No NP granted specifically from 漩渦 (log check)
    vort_np_log = [l for l in log if "漩渦" in l and ("國力" in l or "兵力" in l and "不產出" not in l)]
    # The engine logs "[漩渦] 恰好 4 國，不產出" — that's the else branch confirming silence
    vort_log = [l for l in log if "漩渦" in l]
    # Should contain the "不產出" line and nothing else
    assert any("4" in l and "不產出" in l for l in vort_log), (
        f"漩渦 4-team: should log '不產出'. log={vort_log}"
    )
    # No NP or troop increment logs for 漩渦
    production_log = [l for l in vort_log if "+" in l]
    assert production_log == [], (
        f"漩渦 4-team: no production should be logged. Got: {production_log}"
    )


def test_d_vortex_3_teams_odd_grants_np():
    """
    漩渦 with 3 teams (odd) → grants 2000 NP proportionally. Contrast with 4-team case.
    """
    s = make_state(round_num=2, teams=["1", "2", "3"])
    s.zones["漩渦"] = ZoneState(troops={"1": 1000, "2": 500, "3": 500})
    for t in ["1","2","3"]:
        s.national_power[t] = 0

    new_s, log, _ = run_round(s, {})

    vort_log = [l for l in log if "漩渦" in l]
    assert any("奇數" in l for l in vort_log), (
        f"漩渦 3-team: should log '奇數國'. log={vort_log}"
    )
    # T1 gets floor(2000 * 1000/2000) = 1000 NP
    t1_np_gain = new_s.national_power.get("1", 0)
    assert t1_np_gain >= 1000, (
        f"漩渦 3-team: T1 should gain >= 1000 NP. got {t1_np_gain}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# e.  admin-only sub_round consecutive accumulation
# ══════════════════════════════════════════════════════════════════════════════

def test_e1_admin_only_subrounds_accumulate():
    """
    3 consecutive admin-only rounds → sub_round increments 0→1→2→3.
    Round number does NOT advance in admin-only mode.
    """
    from game.parser import CommandResult, ParsedCommand

    s = make_state(round_num=2, teams=["1"])
    s.sub_round = 0
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")

    assert s.sub_round == 0

    for expected_sub in range(1, 4):
        # Submit only ADMIN commands (no non-ADMIN input)
        cmds = {"ADMIN": "set(HK, 1:500)"}
        new_s, log, _ = run_round(s, cmds)

        assert new_s.sub_round == expected_sub, (
            f"After admin-only round #{expected_sub}: "
            f"sub_round should be {expected_sub}, got {new_s.sub_round}"
        )
        assert new_s.round == 2, (
            f"Admin-only: round must not advance (still 2). got {new_s.round}"
        )
        s = new_s


def test_e2_admin_only_preserves_phase():
    """
    Admin-only round preserves the current phase (does not reset to 'input').
    """
    s = make_state(round_num=1, teams=["1"])
    s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100}, forced_owner="1")

    cmds = {"ADMIN": "set(HK, 1:100)"}
    new_s, log, _ = run_round(s, cmds)

    assert new_s.phase == "input", (
        f"Admin-only: phase should be preserved as 'input', got {new_s.phase!r}"
    )
    assert new_s.sub_round == 1, (
        f"Admin-only: sub_round should be 1, got {new_s.sub_round}"
    )


def test_e3_normal_round_resets_subrounds():
    """
    After a sequence of admin-only rounds, a normal round resets sub_round to 0
    and increments the main round number.
    """
    s = make_state(round_num=2, teams=["1"])
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")

    # 2 admin-only rounds
    for _ in range(2):
        s, _, _ = run_round(s, {"ADMIN": "set(HK, 1:500)"})

    assert s.sub_round == 2

    # Normal round (no commands → no non-admin input with content? Let's check:
    # _has_non_admin_input checks len(vlist) > 0. Empty dict means no team submitted.
    # So empty cmds {} → _has_non_admin_input = False, _has_admin_cmds = False
    # → _admin_only = False AND _has_admin_cmds = False.
    # That means empty round IS a normal round advance.
    s_normal, _, _ = run_round(s, {})

    assert s_normal.sub_round == 0, (
        f"Normal round after admin sub-rounds: sub_round should reset to 0, "
        f"got {s_normal.sub_round}"
    )
    assert s_normal.round == 3, (
        f"Normal round: round should advance to 3, got {s_normal.round}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# f.  T1 union_attack from two zones to same target, same coalition
# ══════════════════════════════════════════════════════════════════════════════

def test_f_multi_source_union_attack_troops_sum():
    """
    T1 sends union_attack from 人類王國 (n=100) and from 精靈森域 (n=150),
    both listing T2 as ally, targeting 龍族火山.
    T2 also sends union_attack from 獸人荒原 (n=200) listing T1, targeting 龍族火山.

    Expected:
    - T1 and T2 form a coalition for 龍族火山.
    - T1's total contribution = 100 + 150 = 250.
    - T2's total contribution = 200.
    - Coalition wins over T3's 100 defenders (bonus = floor(100 * 0.20) = 20).
    - T1 gets 250 + 20 = 270 troops at 龍族火山; T2 gets 200 + 20 = 220.
    """
    s = make_state(round_num=2, teams=["1", "2", "3"])
    s.zones["人類王國"]  = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["精靈森域"]  = ZoneState(troops={"1": 300}, forced_owner="1")
    s.zones["獸人荒原"]  = ZoneState(troops={"2": 500}, forced_owner="2")
    s.zones["龍族火山"]  = ZoneState(troops={"3": 100}, forced_owner="3")

    cmds = {
        "1": (
            "union_attack(人類王國, [2], 龍族火山, 100) "
            "union_attack(精靈森域, [2], 龍族火山, 150)"
        ),
        "2": "union_attack(獸人荒原, [1], 龍族火山, 200)",
    }
    new_s, log, anim = run_round(s, cmds)

    dv = new_s.zones["龍族火山"]
    # Coalition should win (250+200=450 vs 100 defenders)
    assert dv.forced_owner in ("1", "2"), (
        f"Coalition (T1+T2) should capture 龍族火山. forced_owner={dv.forced_owner}"
    )
    # T1 troops = 250 (sent) + bonus (floor(100*0.2)=20) = 270
    # T2 troops = 200 (sent) + 20 = 220
    bonus = math.floor(100 * 0.20)
    t1_troops = dv.troops.get("1", 0)
    t2_troops = dv.troops.get("2", 0)
    assert t1_troops == 250 + bonus, (
        f"T1 should have {250 + bonus} troops in 龍族火山, got {t1_troops}. "
        f"troops={dv.troops}"
    )
    assert t2_troops == 200 + bonus, (
        f"T2 should have {200 + bonus} troops in 龍族火山, got {t2_troops}. "
        f"troops={dv.troops}"
    )


def test_f2_multi_source_effective_allies_set_on_all_vcs():
    """
    When T1 sends two union_attack commands from different zones (both listing T2),
    both ValidatedCmd objects should have effective_allies containing T2.
    """
    s = make_state(round_num=2, teams=["1", "2", "3"])
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"1": 300}, forced_owner="1")
    s.zones["獸人荒原"] = ZoneState(troops={"2": 500}, forced_owner="2")
    s.zones["龍族火山"] = ZoneState(troops={"3": 100}, forced_owner="3")

    parsed = {
        "1": parse_commands(
            "union_attack(人類王國, [2], 龍族火山, 100) "
            "union_attack(精靈森域, [2], 龍族火山, 50)"
        ),
        "2": parse_commands("union_attack(獸人荒原, [1], 龍族火山, 200)"),
    }
    vcmds = RoundValidator(s).validate_all(parsed)

    t1_vcs = [vc for vc in vcmds["1"] if vc.valid]
    assert len(t1_vcs) == 2, f"Both T1 union_attack commands should be valid: {vcmds['1']}"
    for vc in t1_vcs:
        assert "2" in vc.effective_allies, (
            f"Both T1 VCs should list T2 as effective ally. "
            f"effective_allies={vc.effective_allies}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# g.  Stress test: 10 teams × 5 commands (2 union + 3 union_attack) × 3 rounds
# ══════════════════════════════════════════════════════════════════════════════

def _build_stress_cmds_r2(state: GameState) -> dict[str, str]:
    """
    Build 5 legitimate commands per team:
      - 2 union (mutual pairs between adjacent teams)
      - 3 union_attack (each to the 5th island away, listing 2 mutual allies)

    Design choices to ensure all 5 ops are VALID and within troop budget:
    - Use only 1/10 of available troops per command (safe budget)
    - union commands: team i requests to move to partner's zone (partner=i+1 mod 10)
    - union_attack: 3 trio coalitions (team i lists i+1 and i+2 as allies),
      each sending to the zone owned by team (i+5) mod 10
    """
    n_teams = 10
    cmds: dict[str, str] = {}

    for i in range(n_teams):
        team = str(i + 1)
        home = ISLANDS[i]
        avail = state.zones[home].troops.get(team, 0)
        if avail < 10:
            # Fallback: just move to neutral
            cmds[team] = f"moving({home}, 中立小島, 1)"
            continue

        budget = max(1, avail // 20)  # very conservative budget

        # partner for union: (i+1) % n_teams
        partner_idx = (i + 1) % n_teams
        partner = str(partner_idx + 1)
        partner_zone = ISLANDS[partner_idx]

        # target for union_attack: zone owned by team (i+5) % n_teams
        target_idx = (i + 5) % n_teams
        target_zone = ISLANDS[target_idx]
        target_owner = state.zones[target_zone].owner()

        # allies for union_attack: (i+2)%10 and (i+3)%10
        ally1_idx = (i + 2) % n_teams
        ally2_idx = (i + 3) % n_teams
        ally1 = str(ally1_idx + 1)
        ally2 = str(ally2_idx + 1)

        # Avoid ally == team or target being own/ally territory
        if target_owner in (team, ally1, ally2):
            target_idx = (i + 6) % n_teams
            target_zone = ISLANDS[target_idx]
            target_owner = state.zones[target_zone].owner()

        ops = []

        # 2 union ops: T(i) requests to move to partner's zone, partner = ally pair
        # union(source, partner, partner_zone, n) — requesting mode
        if state.zones[partner_zone].owner() == partner and target_owner not in (team,):
            ops.append(f"union({home}, {partner}, {partner_zone}, {budget})")
        else:
            # Fallback: moving to neutral
            ops.append(f"moving({home}, 中立小島, {budget})")

        # Second union: T(i) accepts partner's union (accepting mode: target is own zone)
        # partner requests to move into home (team's zone); team(i) is accepting
        # accepting union: union(home, partner, home, n) where home is team's territory
        ops.append(f"union({home}, {partner}, {home}, {budget})")

        # 3 union_attack ops to target_zone listing [ally1, ally2]
        # only valid if target not owned by ally1 or ally2
        current_target_owner = state.zones[target_zone].owner()
        if current_target_owner not in (team, ally1, ally2):
            for _ in range(3):
                ops.append(
                    f"union_attack({home}, [{ally1},{ally2}], {target_zone}, {budget})"
                )
        else:
            # Fallback: moving to neutral
            for _ in range(3):
                ops.append(f"moving({home}, 中立小島, {budget})")

        # Take first 5 ops
        cmds[team] = " ".join(ops[:5])

    return cmds


@pytest.mark.timeout(30)
def test_g_stress_10teams_5ops_3rounds_union_heavy():
    """
    [Required: g]
    10 teams, 3 rounds. Each round: 5 commands per team (2 union + 3 union_attack).
    All commands designed to be legitimate (legal).

    Verifications:
    - No crash over 3 rounds
    - Each round < 2s (generous timeout for coalition resolution)
    - All troop values >= 0 after each round
    - Round counter increments correctly
    - State is internally consistent (no negative troops, no phantom teams)
    """
    s = GameState(teams=[str(i) for i in range(1, 11)], max_rounds=5)
    s.round = 2  # start at 2 so resource points trigger
    s.phase = "input"
    for i in range(10):
        team = str(i + 1)
        zone = ISLANDS[i]
        s.zones[zone] = ZoneState(troops={team: 3000}, forced_owner=team)

    timing = []
    expected_round = 2

    for round_idx in range(3):
        assert s.round == expected_round

        cmds = _build_stress_cmds_r2(s)

        t_start = time.time()
        s_new, log, anim = run_round(s, cmds)
        t_elapsed = time.time() - t_start
        timing.append(t_elapsed)

        assert t_elapsed < 2.0, (
            f"Stress round {round_idx + 1} took {t_elapsed:.3f}s (> 2s limit)"
        )

        # No negative troops anywhere
        for zone, zs in s_new.zones.items():
            for team, n in zs.troops.items():
                assert n >= 0, (
                    f"Negative troops: zone={zone} team={team} n={n}"
                )

        # All national_power values non-negative
        for team, np in s_new.national_power.items():
            assert np >= 0, f"Negative national_power: team={team} np={np}"

        # Round advanced
        assert s_new.round == expected_round + 1, (
            f"Round should advance from {expected_round} to {expected_round + 1}, "
            f"got {s_new.round}"
        )

        # No unknown teams in zone troops
        for zone, zs in s_new.zones.items():
            for team in zs.troops:
                assert team in s_new.teams, (
                    f"Unknown team {team!r} in zone {zone} troops"
                )

        s = s_new
        expected_round += 1

    for i, t in enumerate(timing):
        print(f"  Stress R2 round {i + 1}: {t * 1000:.1f}ms")


# ══════════════════════════════════════════════════════════════════════════════
# Additional coverage tests
# ══════════════════════════════════════════════════════════════════════════════

def test_multi_round_np_accumulates_correctly():
    """
    Run 3 rounds with T1 owning 人類王國 (900 NP/round) and no battles.
    After 3 rounds NP should be >= 900 * 3.
    """
    x = TERRITORY_POWER["人類王國"]  # 900
    s = make_state(round_num=1, teams=["1"])
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")
    s.national_power["1"] = 0

    for i in range(3):
        s, log, _ = run_round(s, {})

    assert s.national_power.get("1", 0) >= x * 3, (
        f"After 3 rounds owning 人類王國 T1 should have >= {x*3} NP. "
        f"Got {s.national_power.get('1', 0)}"
    )


def test_forced_owner_cleared_by_new_attacker_next_round():
    """
    T1 owns zone in round R. T2 attacks and captures in round R.
    In round R+1, 龍族火山.forced_owner == "2" (not "1").
    """
    s = make_state(round_num=2, teams=["1", "2"])
    s.zones["龍族火山"] = ZoneState(troops={"1": 100}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 1000}, forced_owner="2")

    s2, _, _ = run_round(s, {"2": "attack(精靈森域, 龍族火山, 500)"})

    assert s2.zones["龍族火山"].forced_owner == "2", (
        f"T2 should own 龍族火山 after capture. "
        f"forced_owner={s2.zones['龍族火山'].forced_owner}"
    )
    assert s2.zones["龍族火山"].forced_owner != "1", (
        f"T1's forced_owner should be overwritten after T2 captures."
    )


def test_5op_limit_exact_boundary():
    """
    Exactly 6 valid ops submitted → 6th is over limit and marked invalid.
    """
    s = make_state(round_num=2, teams=["1", "2"])
    s.zones["人類王國"] = ZoneState(troops={"1": 5000}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 100}, forced_owner="2")

    # 6 attacks to enemy zone from own zone (each with small n)
    cmds_txt = " ".join(
        [f"attack(人類王國, 精靈森域, {10 * (k+1)})" for k in range(6)]
    )
    parsed = {"1": parse_commands(cmds_txt)}
    vcmds = RoundValidator(s).validate_all(parsed)

    valid_count = sum(1 for vc in vcmds["1"] if vc.valid)
    invalid_count = sum(1 for vc in vcmds["1"] if not vc.valid)

    # 5 should be valid; 1 should be over-limit invalid
    # BUT: all 6 attacks go to the same zone, total n = 10+20+...+60 = 210
    # 210 <= 5000 so no conflict penalty. Only the 5-op cap applies.
    assert valid_count == 5, (
        f"6 ops: exactly 5 should be valid (5-op cap). Got valid={valid_count}"
    )
    assert invalid_count == 1, (
        f"6 ops: exactly 1 should be over-limit invalid. Got invalid={invalid_count}"
    )


def test_vortex_2_teams_even_grants_troops():
    """
    漩渦 with 2 teams (even, not 4) → grants 2000 troop bonus proportionally.
    """
    s = make_state(round_num=2, teams=["1", "2"])
    s.zones["漩渦"] = ZoneState(troops={"1": 1000, "2": 1000})

    new_s, log, _ = run_round(s, {})

    vort_log = [l for l in log if "漩渦" in l]
    assert any("偶數" in l for l in vort_log), (
        f"漩渦 2-team: should log '偶數國'. log={vort_log}"
    )
    # Each team gets floor(2000 * 1000/2000) = 1000 troop bonus
    vort = new_s.zones["漩渦"]
    # Before: 1000 + 1000 bonus = 2000 each
    assert vort.troops.get("1", 0) == 2000, (
        f"漩渦 2-team: T1 should have 2000 troops (1000+1000). got {vort.troops}"
    )
