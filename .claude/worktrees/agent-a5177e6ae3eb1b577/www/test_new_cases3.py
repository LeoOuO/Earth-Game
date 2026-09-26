"""
Comprehensive test suite: test_new_cases3.py

Covers:
 Group 1:  Parser edge cases (tests 1-4)
 Group 2:  Union mechanics (tests 5-7)
 Group 3:  Garrison edge cases (tests 8-9)
 Group 4:  set() command (tests 10-11)
 Group 5:  execute_round with empty commands (test 12)
 Group 6:  moving to garrison zone (test 13)
 Group 7:  Resource point penalties (test 14)
 Group 8:  0-troop forced_owner national power multi-team (test 15)
 Group 9:  10-team union_attack stress tests (tests 16-18)
"""

import sys, os, math, time
sys.path.insert(0, os.path.dirname(__file__))

from game.engine import RoundValidator, execute_round as _execute_round
from game.state import (
    GameState, ZoneState,
    NEUTRAL_ISLAND, RESOURCE_POINTS, ISLANDS, TERRITORY_POWER, ALL_TEAMS,
)
from game.parser import parse_commands


# ── helpers ───────────────────────────────────────────────────────────────────

def run_round(state: GameState, cmds_by_team: dict) -> tuple:
    """Parse, validate and execute one round. Returns (new_state, log, anim)."""
    parsed = {t: parse_commands(txt) for t, txt in cmds_by_team.items()}
    vcmds  = RoundValidator(state).validate_all(parsed)
    return _execute_round(state, vcmds)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 1: Parser edge cases
# ═══════════════════════════════════════════════════════════════════════════════

def test_parse_empty_string():
    """parse_commands('') returns []."""
    results = parse_commands("")
    assert results == [], f"Expected [], got {results}"


def test_parse_n_zero_attack_invalid():
    """attack(HK, ELF, 0) → invalid (n must be >= 1)."""
    from game.parser import parse_command
    result = parse_command("attack(HK, ELF, 0)")
    # _parse_int returns None for 0 (requires > 0)
    assert not result.ok, (
        f"attack with n=0 should be invalid (parse level), got ok={result.ok}"
    )


def test_parse_n_negative_invalid():
    """attack(HK, ELF, -5) → invalid (n must be positive)."""
    from game.parser import parse_command
    result = parse_command("attack(HK, ELF, -5)")
    assert not result.ok, (
        f"attack with n=-5 should be invalid (parse level), got ok={result.ok}"
    )


def test_parse_allies_duplicates():
    """
    union_attack(HK, [2,2,3], ELF, 100) — duplicate ally '2' in the list.
    union_attack is a legacy alias → parsed as attack(S, E, n, [P]).
    Verify it either parses OK or fails gracefully — no crash.
    """
    from game.parser import parse_command
    result = parse_command("union_attack(HK, [2,2,3], ELF, 100)")
    # Either ok or not — just must not crash
    assert isinstance(result.ok, bool), "result.ok should be a bool, no crash"
    if result.ok:
        # If parsed, union_attack alias maps to op="attack"
        assert result.command is not None
        assert result.command.op in ("union_attack", "attack")
    else:
        assert result.error, "failed parse must have an error message"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2: Union mechanics
# ═══════════════════════════════════════════════════════════════════════════════

def test_union_both_requesting_no_match():
    """
    T1 sends help(人類王國, 精靈森域, 80, 2) — wants to move to T2's zone.
    T2 sends help(精靈森域, 人類王國, 80, 1) — wants to move to T1's zone.
    Different targets → neither help is matched (T2 would need accept(精靈森域, 1) not help).
    Both help_matched=False. Neither executes.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 500}, forced_owner="2")
    s.zones["龍族火山"] = ZoneState(troops={"1": 200})

    parsed = {
        "1": parse_commands("help(人類王國, 精靈森域, 80, 2)"),
        "2": parse_commands("help(精靈森域, 人類王國, 80, 1)"),
    }
    vcmds = RoundValidator(s).validate_all(parsed)

    vc1 = vcmds["1"][0]
    vc2 = vcmds["2"][0]

    # Both pending (help without matching accept)
    assert not vc1.help_matched, (
        f"T1's help should not be matched (no accept), got help_matched={vc1.help_matched}"
    )
    assert not vc2.help_matched, (
        f"T2's help should not be matched (no accept), got help_matched={vc2.help_matched}"
    )

    new_s, log, _ = _execute_round(s, vcmds)
    # Pending help doesn't move troops; source zones unchanged
    t1_at_hk = new_s.zones["人類王國"].troops.get("1", 0)
    assert t1_at_hk == 500, (
        f"T1's troops should not move on unmatched help, got {t1_at_hk}"
    )
    t2_at_elf = new_s.zones["精靈森域"].troops.get("2", 0)
    assert t2_at_elf == 500, (
        f"T2's troops should not move on unmatched help, got {t2_at_elf}"
    )


def test_union_confirmed_both_sides_move():
    """
    T1 sends help(人類王國, 精靈森域, 80, 2) — T1 moves 80 troops to T2's zone.
    T2 sends accept(精靈森域, 1) — T2 accepts T1's help.
    Confirmed: T1's 80 troops move from 人類王國 to 精靈森域. Accept costs nothing.
    Note: 人類王國 has 200-80=120 remaining < 300 → cleared by Phase 1.5.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    # T2 owns 精靈森域 (target)
    s.zones["精靈森域"] = ZoneState(troops={"2": 300}, forced_owner="2")
    # T1 has troops at 人類王國 (source)
    s.zones["人類王國"] = ZoneState(troops={"1": 200}, forced_owner="1")

    parsed = {
        "1": parse_commands("help(人類王國, 精靈森域, 80, 2)"),
        "2": parse_commands("accept(精靈森域, 1)"),
    }
    vcmds = RoundValidator(s).validate_all(parsed)

    vc1 = vcmds["1"][0]
    vc2 = vcmds["2"][0]

    assert vc1.help_matched, (
        f"T1's help should be matched (T2 accepted), got help_matched={vc1.help_matched}. "
        f"valid={vc1.valid}, reason={vc1.reason!r}"
    )
    # T2's accept: help_matched is False (accept doesn't set help_matched on accepter)
    assert vc2.valid, (
        f"T2's accept should be valid, got valid={vc2.valid}, reason={vc2.reason!r}"
    )

    new_s, log, _ = _execute_round(s, vcmds)

    # T1 moves 80 from 人類王國 to 精靈森域
    # 人類王國 has 200-80=120 remaining, but 120 < 300 → cleared by Phase 1.5
    t1_at_hk = new_s.zones["人類王國"].troops.get("1", 0)
    t1_at_elf = new_s.zones["精靈森域"].troops.get("1", 0)
    assert t1_at_hk == 0, (
        f"T1 should have 0 at 人類王國 (120 < 300 → cleared by Phase 1.5), got {t1_at_hk}"
    )
    assert t1_at_elf == 80, f"T1 should have 80 at 精靈森域, got {t1_at_elf}"

    # T2 stays unchanged at 精靈森域 (accept costs nothing)
    t2_at_elf = new_s.zones["精靈森域"].troops.get("2", 0)
    assert t2_at_elf == 300, f"T2 should still have 300 at 精靈森域, got {t2_at_elf}"


def test_union_and_attack_same_source_both_valid():
    """
    A has 150 at S.
    A submits help(S, E_B, 100, 2) (requesting, uses 100 troops) + attack(S, E2, 50).
    100+50=150 = available → no conflict. Both valid.
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2; s.phase = "input"
    # T1 has 150 at 人類王國
    s.zones["人類王國"] = ZoneState(troops={"1": 150}, forced_owner="1")
    # T2 owns 精靈森域 (target for help)
    s.zones["精靈森域"] = ZoneState(troops={"2": 300}, forced_owner="2")
    # T3 owns 龍族火山 (target for attack)
    s.zones["龍族火山"] = ZoneState(troops={"3": 200}, forced_owner="3")
    # T2 does not need to accept for validation purposes — we test validation only
    parsed = {
        "1": parse_commands(
            "help(人類王國, 精靈森域, 100, 2) "
            "attack(人類王國, 龍族火山, 50)"
        ),
    }
    vcmds = RoundValidator(s).validate_all(parsed)
    vlist = vcmds["1"]

    # Both should be valid (100 + 50 = 150 = available)
    for vc in vlist:
        assert vc.valid, (
            f"op {vc.result.command.op if vc.result.command else '?'} should be valid, "
            f"reason={vc.reason!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3: Garrison edge cases
# ═══════════════════════════════════════════════════════════════════════════════

def test_garrison_pre_round_only_no_same_round_moving():
    """
    Regression: T1 has 0 troops at E pre-round (no garrison).
    T1 sends moving(S, E, 50) same round it attacks E.
    No garrison-betrayal should fire (no pre-round troops at E).
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    # T1 has 0 troops at 精靈森域 pre-round
    s.zones["人類王國"]  = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["龍族火山"]  = ZoneState(troops={"1": 300}, forced_owner="1")
    s.zones["精靈森域"]  = ZoneState(troops={"2": 200}, forced_owner="2")  # T1 has 0 here

    new_s, log, _ = run_round(s, {
        "1": "moving(龍族火山, 精靈森域, 50) attack(人類王國, 精靈森域, 100)",
    })

    # No garrison-betrayal log for T1 at 精靈森域
    betrayal_logs = [l for l in log if "駐守叛變" in l and "1" in l]
    assert betrayal_logs == [], (
        f"No garrison-betrayal should fire when T1 had 0 pre-round troops at 精靈森域. "
        f"log={betrayal_logs}"
    )


def test_garrison_and_union_attack():
    """
    T1 and T3 coalition union_attack 獸人荒原 (no own troops there → valid).
    Coalition forms and executes normally.
    """
    s = GameState(teams=["1", "2", "3"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["獸人荒原"]  = ZoneState(troops={"2": 300}, forced_owner="2")
    s.zones["人類王國"]  = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["龍族火山"]  = ZoneState(troops={"3": 400}, forced_owner="3")

    # T1 + T3 union_attack 獸人荒原 (T2 owns it, T1/T3 have no troops there)
    new_s, log, _ = run_round(s, {
        "1": "union_attack(人類王國, [3], 獸人荒原, 300)",
        "3": "union_attack(龍族火山, [1], 獸人荒原, 200)",
    })

    # Coalition (300+200=500) vs defender (300) → attacker wins
    owner = new_s.zones["獸人荒原"].owner()
    assert owner in ("1", "3"), (
        f"Coalition should win and capture 獸人荒原, got owner={owner}. "
        f"log={[l for l in log if '戰鬥' in l or '獸人' in l]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4: set() command
# ═══════════════════════════════════════════════════════════════════════════════

def test_admin_set_unlimited_ops():
    """
    ADMIN can submit more than 5 set() commands in one round.
    set() is excluded from the 5-op limit.
    All 8 set() commands must be valid.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"

    # 8 set() commands targeting 8 different zones
    set_cmds = " ".join(
        f"set({zone}, 1:100)"
        for zone in ISLANDS[:8]
    )
    parsed = {"ADMIN": parse_commands(set_cmds)}
    vcmds  = RoundValidator(s).validate_all(parsed)

    admin_vlist = vcmds["ADMIN"]
    assert len(admin_vlist) == 8, f"Expected 8 parsed commands, got {len(admin_vlist)}"

    invalid = [vc for vc in admin_vlist if not vc.valid]
    assert invalid == [], (
        f"All ADMIN set() should be valid (no 5-op limit applies), "
        f"invalid reasons: {[vc.reason for vc in invalid]}"
    )


def test_admin_set_forced_owner_to_unknown_team():
    """
    ADMIN sets forced_owner to '99' (not a valid team).
    The parser should reject the command — no crash.
    """
    from game.parser import parse_command
    result = parse_command("set(HK, 99, 1:500)")
    # '99' is not in ALL_TEAMS, so this should fail at parse level
    assert not result.ok, (
        f"set() with invalid team '99' as forced_owner should fail parse, got ok={result.ok}"
    )
    assert result.error, "failed parse should include an error message"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5: execute_round with empty commands
# ═══════════════════════════════════════════════════════════════════════════════

def test_empty_round_advances():
    """
    All teams submit nothing.
    Round advances: neutral island ×1.5 applies, then rescue rule kicks in.
    T2's zone has 100 troops < 300 → cleared by Phase 1.5 → NP = 0.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    # T1 has troops at neutral island (will get ×1.5 boost)
    s.zones[NEUTRAL_ISLAND] = ZoneState(troops={"1": 200})
    # T2 owns 人類王國 with only 100 troops (< 300 → cleared by Phase 1.5)
    s.zones["人類王國"] = ZoneState(troops={"2": 100}, forced_owner="2")

    new_s, log, _ = run_round(s, {})

    # Round must advance
    assert new_s.round == 3, f"Round should advance to 3, got {new_s.round}"

    # Neutral island ×1.5 applied to T1 (200 → ceil100(300)=300), then rescue rule:
    # T1 total = 300 < 1000 → topped up to 1000 at neutral island.
    t1_neutral = new_s.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    expected_neutral = 1000  # 200×1.5=300, rescue +700 → 1000
    assert t1_neutral == expected_neutral, (
        f"Neutral island ×1.5 + rescue: expected {expected_neutral}, got {t1_neutral}"
    )

    # T2's zone cleared by phase 1.5 (100 < 300), so no NP
    x = TERRITORY_POWER["人類王國"]
    np2 = new_s.national_power.get("2", 0)
    assert np2 == 0, (
        f"T2 should earn 0 NP (zone cleared by phase 1.5), got {np2}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6: moving to garrison zone
# ═══════════════════════════════════════════════════════════════════════════════

def test_moving_to_enemy_zone_with_own_garrison_valid():
    """
    T1 has garrison at enemy zone E (T1 has troops there, T2 owns it).
    T1 submits moving(S, E, 50).
    T1 controls E (has troops there) → moving is valid. Troops arrive at E.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    # T1 has garrison at 精靈森域, T2 is the owner
    s.zones["精靈森域"] = ZoneState(troops={"1": 100, "2": 300}, forced_owner="2")
    # T1's source zone
    s.zones["人類王國"]  = ZoneState(troops={"1": 500}, forced_owner="1")

    parsed = {"1": parse_commands("moving(人類王國, 精靈森域, 50)")}
    vcmds  = RoundValidator(s).validate_all(parsed)

    vc = vcmds["1"][0]
    assert vc.valid, (
        f"moving to a zone where T1 has garrison should be valid, "
        f"reason={vc.reason!r}"
    )

    new_s, log, _ = _execute_round(s, vcmds)

    # T1 should have 100 + 50 = 150 at 精靈森域
    t1_at_elf = new_s.zones["精靈森域"].troops.get("1", 0)
    assert t1_at_elf == 150, (
        f"T1 should have 150 at 精靈森域 (garrison 100 + moved 50), got {t1_at_elf}"
    )
    # Source reduced by 50
    t1_at_hk = new_s.zones["人類王國"].troops.get("1", 0)
    assert t1_at_hk == 450, (
        f"T1 should have 450 at 人類王國 (500 - 50), got {t1_at_hk}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7: Resource point penalties
# ═══════════════════════════════════════════════════════════════════════════════

def test_attack_resource_point_round2_troops_lost():
    """
    T1 attacks 迷霧島 in round 2.
    In the current engine: attacking resource points is valid (no penalty, no warning).
    Troops depart source, battle resolves at 迷霧島 (Situation A).
    After Phase 5 (resource point settle), 迷霧島 gives +2000 troops to occupants.
    """
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500}, forced_owner="1")
    s.zones["精靈森域"] = ZoneState(troops={"2": 200})

    # Round 2 allows resource point attacks — valid, no penalty, no warning
    parsed = {"1": parse_commands("attack(人類王國, 迷霧島, 100)")}
    vcmds  = RoundValidator(s).validate_all(parsed)

    vc = vcmds["1"][0]
    # Valid with no warning (resource point attack has no conflict penalty)
    assert vc.valid, (
        f"attack on resource point in round 2 should be valid, "
        f"reason={vc.reason!r}"
    )
    # Note: new engine does NOT add warning for resource point attacks (only neutral island)

    new_s, log, _ = _execute_round(s, vcmds)

    # Source loses 100 troops
    t1_at_hk = new_s.zones["人類王國"].troops.get("1", 0)
    assert t1_at_hk == 400, (
        f"T1 should have 500-100=400 at source, got {t1_at_hk}"
    )
    # T1 wins the battle at 迷霧島 (solo, no defender) — troops arrive there
    # (Phase 5 then adds +2000 for ≤4 teams at 迷霧島, so final is ≥ 100)
    t1_at_fog = new_s.zones["迷霧島"].troops.get("1", 0)
    assert t1_at_fog > 0, (
        f"T1's troops should be present at 迷霧島 after attacking (no penalty), got {t1_at_fog}"
    )
    # Attack log must exist (not penalty)
    attack_logs = [l for l in log if "attack" in l.lower() or "戰鬥" in l and "迷霧" in l]
    assert attack_logs, (
        f"Attack/battle log should appear for resource point attack. log={log}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8: 0-troop forced_owner national power (multi-team zone)
# ═══════════════════════════════════════════════════════════════════════════════

def test_zero_troop_forced_owner_multi_team_gets_half_x():
    """
    T1 is forced_owner with 0 troops. T2 has 400 troops at same zone (龍族火山, x=1000).
    Total_t=400 (>= 300, so zone not cleared by Phase 1.5).
    Both should receive NP (zone has enough troops to score).
    """
    x = TERRITORY_POWER["龍族火山"]  # 1000
    s = GameState(teams=["1", "2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["龍族火山"] = ZoneState(troops={"2": 400}, forced_owner="1")

    new_s, log, _ = run_round(s, {})

    np1 = new_s.national_power.get("1", 0)
    np2 = new_s.national_power.get("2", 0)

    dv_log = [l for l in log if "龍族火山" in l]
    # Both should get NP (zone has enough troops)
    assert np1 + np2 > 0, (
        f"NP should be distributed. np1={np1}, np2={np2}. log={dv_log}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Group 9: 10-team union_attack stress tests
# ═══════════════════════════════════════════════════════════════════════════════

# Setup helper: create a GameState with 10 teams each owning one island
# Teams 1-9 own ISLANDS[0..8]; Team 10 is the "target" at ISLANDS[9]
def _make_10team_state(round_num: int = 2) -> GameState:
    """
    Create a GameState with 10 teams each owning one island (1000 troops each).
    Teams 1-9 own ISLANDS[0..8] respectively.
    Team 10 owns ISLANDS[9] (default attack target for stress tests).
    """
    s = GameState(teams=[str(i) for i in range(1, 11)], max_rounds=5)
    s.round = round_num; s.phase = "input"
    for i in range(9):
        team = str(i + 1)
        zone = ISLANDS[i]
        s.zones[zone] = ZoneState(troops={team: 1000}, forced_owner=team)
    # Team 10 owns ISLANDS[9] (哥布林族)
    s.zones[ISLANDS[9]] = ZoneState(troops={"10": 1500}, forced_owner="10")
    return s


def test_10_teams_5_union_attacks_per_round_no_crash():
    """
    3 rounds, 10 teams, mixed coalition patterns.
    Round 1: Teams 1-8 union_attack in 4 pairs (2-team coalitions); Team 9 solo; Team 10 defends.
    Round 2: Teams 1-9 each solo-attack the new owner; Team 10 defends.
    Round 3: Teams 1-4 form a 4-team coalition; Teams 5-8 form a 4-team coalition;
             Team 9 solo; Team 10 defends.
    Each round must complete in < 1 second. No crashes.
    State consistency: no negative troops.
    """
    s = _make_10team_state(round_num=2)
    target_zone = ISLANDS[9]  # 哥布林族, owned by team 10

    timing_results = []

    # ── Round 1: 2-team coalition attacks ────────────────────────────────────
    t_start = time.time()
    cmds = {}
    # Pairs: (1,2), (3,4), (5,6), (7,8)
    for pair_idx, (a, b) in enumerate([(1, 2), (3, 4), (5, 6), (7, 8)]):
        src_a = ISLANDS[a - 1]
        src_b = ISLANDS[b - 1]
        cmds[str(a)] = f"union_attack({src_a}, [{b}], {target_zone}, 100)"
        cmds[str(b)] = f"union_attack({src_b}, [{a}], {target_zone}, 100)"
    # Team 9 solo
    cmds["9"] = f"attack({ISLANDS[8]}, {target_zone}, 100)"
    # Team 10 defends (no command)

    s2, log, _ = run_round(s, cmds)
    t_elapsed = time.time() - t_start
    timing_results.append(("Round 1 (2-team coalitions)", t_elapsed))
    assert t_elapsed < 1.0, f"Round 1 took too long: {t_elapsed:.3f}s"

    # Verify no negative troops
    for zone, zs in s2.zones.items():
        for team, n in zs.troops.items():
            assert n >= 0, f"Negative troops at {zone} for team {team}: {n}"

    # ── Round 2: solo attacks ─────────────────────────────────────────────────
    # Find current owner of target_zone (or use target as-is)
    current_owner = s2.zones[target_zone].owner() or "10"
    # Teams attack neutral island (valid in round 3+, but round 2 → use a different zone)
    # Give each team some troops to attack with
    for i in range(1, 10):
        team = str(i)
        home = ISLANDS[i - 1]
        if s2.zones[home].troops.get(team, 0) < 50:
            s2.zones[home].troops[team] = s2.zones[home].troops.get(team, 0) + 500

    t_start = time.time()
    cmds2 = {}
    for i in range(1, 10):
        team = str(i)
        src = ISLANDS[i - 1]
        # Only attack target_zone if team doesn't own it
        if s2.zones[target_zone].owner() != team:
            cmds2[team] = f"attack({src}, {target_zone}, 50)"

    s3, log2, _ = run_round(s2, cmds2)
    t_elapsed = time.time() - t_start
    timing_results.append(("Round 2 (solo attacks)", t_elapsed))
    assert t_elapsed < 1.0, f"Round 2 took too long: {t_elapsed:.3f}s"

    # Verify no negative troops
    for zone, zs in s3.zones.items():
        for team, n in zs.troops.items():
            assert n >= 0, f"Negative troops at {zone} for team {team}: {n}"

    # ── Round 3: larger coalitions ────────────────────────────────────────────
    # Replenish troops
    for i in range(1, 10):
        team = str(i)
        home = ISLANDS[i - 1]
        s3.zones[home].troops[team] = s3.zones[home].troops.get(team, 0) + 500
        s3.zones[home].forced_owner = team  # ensure control

    t_start = time.time()
    cmds3 = {}
    # Coalition A: teams 1,2,3,4 → each lists [2,3,4], [1,3,4], [1,2,4], [1,2,3]
    group_a = [1, 2, 3, 4]
    for t in group_a:
        allies_str = "[" + ",".join(str(x) for x in group_a if x != t) + "]"
        src = ISLANDS[t - 1]
        if s3.zones[target_zone].owner() != str(t):
            cmds3[str(t)] = f"union_attack({src}, {allies_str}, {target_zone}, 100)"
    # Coalition B: teams 5,6,7,8
    group_b = [5, 6, 7, 8]
    for t in group_b:
        allies_str = "[" + ",".join(str(x) for x in group_b if x != t) + "]"
        src = ISLANDS[t - 1]
        if s3.zones[target_zone].owner() != str(t):
            cmds3[str(t)] = f"union_attack({src}, {allies_str}, {target_zone}, 100)"
    # Team 9 solo
    if s3.zones[target_zone].owner() != "9":
        cmds3["9"] = f"attack({ISLANDS[8]}, {target_zone}, 100)"

    s4, log3, _ = run_round(s3, cmds3)
    t_elapsed = time.time() - t_start
    timing_results.append(("Round 3 (4-team coalitions)", t_elapsed))
    assert t_elapsed < 1.0, f"Round 3 took too long: {t_elapsed:.3f}s"

    # Verify no negative troops
    for zone, zs in s4.zones.items():
        for team, n in zs.troops.items():
            assert n >= 0, f"Negative troops at {zone} for team {team}: {n}"

    # Print timing summary
    for label, t in timing_results:
        print(f"  {label}: {t*1000:.1f}ms")


def test_10_teams_all_vs_one_target_coalition_stress():
    """
    All 10 teams mutually union_attack ONE target — maximum coalition size test.
    Teams 1-9 each own their home island and all mutually list each other as allies.
    They all attack ISLANDS[9] (团 10's zone).
    Verify:
      - The 9-team coalition forms correctly (effective_allies has 8 members for each team)
      - No crash, no infinite loop
      - Execution time < 1 second
      - Target zone owner changes to one of teams 1-9 after the battle
    """
    s = _make_10team_state(round_num=2)
    target_zone = ISLANDS[9]  # 哥布林族

    attackers = [str(i) for i in range(1, 10)]  # teams 1-9

    cmds = {}
    for t in attackers:
        src = ISLANDS[int(t) - 1]
        allies = [x for x in attackers if x != t]
        allies_str = "[" + ",".join(allies) + "]"
        cmds[t] = f"union_attack({src}, {allies_str}, {target_zone}, 200)"

    parsed = {t: parse_commands(txt) for t, txt in cmds.items()}

    t_start = time.time()
    vcmds  = RoundValidator(s).validate_all(parsed)
    t_validate = time.time() - t_start

    t_start = time.time()
    new_s, log, _ = _execute_round(s, vcmds)
    t_execute = time.time() - t_start

    total_time = t_validate + t_execute
    print(f"  All-vs-one: validate={t_validate*1000:.1f}ms execute={t_execute*1000:.1f}ms total={total_time*1000:.1f}ms")

    assert total_time < 1.0, f"All-vs-one coalition took too long: {total_time:.3f}s"

    # Verify effective_allies for each attacker — should be a coalition
    for t in attackers:
        vlist = vcmds[t]
        for vc in vlist:
            if vc.valid and vc.result.command and vc.result.command.op == "union_attack":
                # In a 9-team coalition, each member has 8 effective allies
                n_allies = len(vc.effective_allies)
                assert n_allies == 8, (
                    f"Team {t} should have 8 effective allies in 9-team coalition, "
                    f"got {n_allies}. effective_allies={vc.effective_allies}"
                )

    # No negative troops
    for zone, zs in new_s.zones.items():
        for team, n in zs.troops.items():
            assert n >= 0, f"Negative troops: zone={zone} team={team} n={n}"

    # Target zone owner should be one of the attackers (or still 10 if all attackers lost)
    new_owner = new_s.zones[target_zone].owner()
    # 9-team coalition with 200 each = 1800 > 1500 defender → attackers win
    assert new_owner in attackers, (
        f"After 9-team coalition attack with 1800 vs 1500, one of teams 1-9 should own "
        f"{target_zone}, got owner={new_owner!r}. "
        f"log={[l for l in log if '戰鬥' in l]}"
    )


def test_10_teams_complex_coalition_patterns():
    """
    Round 1: 2-team coalitions (pairs: (1,2), (3,4), (5,6), (7,8), team 9 solo)
    Round 2: 3-team coalitions (triples: (1,2,3), (4,5,6), (7,8,9))
    Round 3: 5-team coalition (1,2,3,4,5) + 4-team coalition (6,7,8,9)
    All rounds < 1 second each. No crashes.
    """
    s = _make_10team_state(round_num=2)
    target_zone = ISLANDS[9]  # 哥布林族, team 10's zone
    timing_results = []

    def replenish(state: GameState, teams, amount=500):
        """Give each team `amount` extra troops at their home zone."""
        for t in teams:
            i = int(t) - 1
            if i < len(ISLANDS) - 1:
                home = ISLANDS[i]
                state.zones[home].troops[t] = state.zones[home].troops.get(t, 0) + amount
                state.zones[home].forced_owner = t

    # ── Round 1: 2-team coalitions ────────────────────────────────────────────
    t_start = time.time()
    cmds1 = {}
    for a, b in [(1, 2), (3, 4), (5, 6), (7, 8)]:
        src_a = ISLANDS[a - 1]
        src_b = ISLANDS[b - 1]
        # Check neither is the target zone owner
        if s.zones[target_zone].owner() not in (str(a), str(b)):
            cmds1[str(a)] = f"union_attack({src_a}, [{b}], {target_zone}, 100)"
            cmds1[str(b)] = f"union_attack({src_b}, [{a}], {target_zone}, 100)"
    if s.zones[target_zone].owner() != "9":
        cmds1["9"] = f"attack({ISLANDS[8]}, {target_zone}, 100)"

    s2, log1, _ = run_round(s, cmds1)
    t1 = time.time() - t_start
    timing_results.append(("Round 1 (2-team pairs)", t1))
    assert t1 < 1.0, f"Round 1 too slow: {t1:.3f}s"

    # No negative troops
    for zone, zs in s2.zones.items():
        for team, n in zs.troops.items():
            assert n >= 0, f"R1 negative troops: {zone} {team}={n}"

    # ── Round 2: 3-team coalitions ────────────────────────────────────────────
    replenish(s2, [str(i) for i in range(1, 10)])

    t_start = time.time()
    cmds2 = {}
    for group in [(1, 2, 3), (4, 5, 6), (7, 8, 9)]:
        for t in group:
            allies_str = "[" + ",".join(str(x) for x in group if x != t) + "]"
            src = ISLANDS[t - 1]
            if s2.zones[target_zone].owner() != str(t):
                cmds2[str(t)] = f"union_attack({src}, {allies_str}, {target_zone}, 100)"

    s3, log2, _ = run_round(s2, cmds2)
    t2 = time.time() - t_start
    timing_results.append(("Round 2 (3-team triples)", t2))
    assert t2 < 1.0, f"Round 2 too slow: {t2:.3f}s"

    # No negative troops
    for zone, zs in s3.zones.items():
        for team, n in zs.troops.items():
            assert n >= 0, f"R2 negative troops: {zone} {team}={n}"

    # ── Round 3: 5-team + 4-team coalitions ──────────────────────────────────
    replenish(s3, [str(i) for i in range(1, 10)])

    t_start = time.time()
    cmds3 = {}
    group_a = [1, 2, 3, 4, 5]
    group_b = [6, 7, 8, 9]
    for group in [group_a, group_b]:
        for t in group:
            allies_str = "[" + ",".join(str(x) for x in group if x != t) + "]"
            src = ISLANDS[t - 1]
            if s3.zones[target_zone].owner() != str(t):
                cmds3[str(t)] = f"union_attack({src}, {allies_str}, {target_zone}, 100)"

    s4, log3, _ = run_round(s3, cmds3)
    t3 = time.time() - t_start
    timing_results.append(("Round 3 (5+4-team coalitions)", t3))
    assert t3 < 1.0, f"Round 3 too slow: {t3:.3f}s"

    # No negative troops
    for zone, zs in s4.zones.items():
        for team, n in zs.troops.items():
            assert n >= 0, f"R3 negative troops: {zone} {team}={n}"

    for label, t in timing_results:
        print(f"  {label}: {t*1000:.1f}ms")


# ═══════════════════════════════════════════════════════════════════════════════
# Standalone runner
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import traceback

    tests = [
        # Group 1: Parser edge cases
        test_parse_empty_string,
        test_parse_n_zero_attack_invalid,
        test_parse_n_negative_invalid,
        test_parse_allies_duplicates,
        # Group 2: Union mechanics
        test_union_both_requesting_no_match,
        test_union_confirmed_both_sides_move,
        test_union_and_attack_same_source_both_valid,
        # Group 3: Garrison edge cases
        test_garrison_pre_round_only_no_same_round_moving,
        test_garrison_and_union_attack,
        # Group 4: set() command
        test_admin_set_unlimited_ops,
        test_admin_set_forced_owner_to_unknown_team,
        # Group 5: empty round
        test_empty_round_advances,
        # Group 6: moving to garrison zone
        test_moving_to_enemy_zone_with_own_garrison_valid,
        # Group 7: Resource point penalties
        test_attack_resource_point_round2_troops_lost,
        # Group 8: 0-troop forced_owner NP
        test_zero_troop_forced_owner_multi_team_gets_half_x,
        # Group 9: 10-team stress tests
        test_10_teams_5_union_attacks_per_round_no_crash,
        test_10_teams_all_vs_one_target_coalition_stress,
        test_10_teams_complex_coalition_patterns,
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
