"""
Comprehensive tests covering:
  - Parser: set command variants
  - Engine: admin-only detection, penalty attacks, tie-breaking,
            garrison betrayal, forced_owner, moving restrictions,
            neutral island phase, resource points phase
  - app.py: setup, submit, execute, undo/redo via Flask test client
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))

from game.state  import GameState, ZoneState, ALL_ZONES, NEUTRAL_ISLAND, RESOURCE_POINTS
from game.parser import parse_commands
from game.engine import RoundValidator, execute_round


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

PASS = 0; FAIL = 0

def ok(name):
    global PASS; PASS += 1; print(f"PASS  {name}")

def fail(name, msg):
    global FAIL; FAIL += 1; print(f"FAIL  {name}: {msg}")

def check(name, cond, msg=""):
    if cond: ok(name)
    else: fail(name, msg or "assertion failed")

def run_round(state, cmds_by_team: dict):
    """Parse + validate + execute one round. Returns (new_state, log, anim, vcmds)."""
    parsed = {t: parse_commands(txt) for t, txt in cmds_by_team.items()}
    vcmds  = RoundValidator(state).validate_all(parsed)
    new_s, log, anim = execute_round(state, vcmds)
    return new_s, log, anim, vcmds

def simple_state(teams=None, round_=1):
    """Minimal state with given teams. Each team owns one island."""
    teams = teams or ["1","2","3","4"]
    s = GameState(teams=teams, max_rounds=3)
    s.round = round_
    s.phase = "input"
    islands = [z for z in ALL_ZONES if z not in RESOURCE_POINTS and z != NEUTRAL_ISLAND]
    for i, t in enumerate(teams):
        s.zones[islands[i]] = ZoneState(troops={t: 500})
    return s, islands


# ══════════════════════════════════════════════════════════════════════════════
# 1. Parser — set command
# ══════════════════════════════════════════════════════════════════════════════

def test_parser_set_clear():
    """set(HK) → clears all troops, forced_owner unchanged."""
    res = parse_commands("set(HK)")
    check("parser_set_clear_ok",    len(res)==1 and res[0].ok)
    cmd = res[0].command
    check("parser_set_clear_op",    cmd.op == "set")
    check("parser_set_clear_troops", cmd.allies == [])
    # sentinel means forced_owner unchanged
    check("parser_set_clear_fo",    cmd.nation == "\x00")

def test_parser_set_troops_only():
    """set(HK, 1:500) → no forced_owner change, troops set."""
    res = parse_commands("set(HK, 1:500)")
    check("parser_set_troops_ok",    res[0].ok)
    cmd = res[0].command
    check("parser_set_troops_allies", dict(cmd.allies) == {"1": 500})
    check("parser_set_troops_fo",     cmd.nation == "\x00")

def test_parser_set_with_owner():
    """set(HK, 2, 1:300, 2:200) → forced_owner=2, troops set."""
    res = parse_commands("set(HK, 2, 1:300, 2:200)")
    check("parser_set_owner_ok",    res[0].ok)
    cmd = res[0].command
    check("parser_set_owner_k",     cmd.nation == "2")
    check("parser_set_owner_troops", dict(cmd.allies) == {"1": 300, "2": 200})

def test_parser_set_clear_owner():
    """set(HK, 0, 1:500) → forced_owner cleared."""
    res = parse_commands("set(HK, 0, 1:500)")
    check("parser_set_clear_owner_ok", res[0].ok)
    cmd = res[0].command
    check("parser_set_clear_owner_k",  cmd.nation == "")   # "" = clear

def test_parser_set_bad_zone():
    """set(BADZONE) → parse error."""
    res = parse_commands("set(BADZONE)")
    check("parser_set_bad_zone", not res[0].ok)

def test_parser_set_bad_owner():
    """set(HK, 99) → unknown nation error."""
    res = parse_commands("set(HK, 99, 1:100)")
    check("parser_set_bad_owner", not res[0].ok)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Engine — admin-only round detection
# ══════════════════════════════════════════════════════════════════════════════

def test_empty_round_advances():
    """No commands at all → normal round advance (not intermediate)."""
    s, islands = simple_state(["1","2"])
    s2, log, _, _ = run_round(s, {})
    check("empty_round_advances",     s2.round == 2 and s2.sub_round == 0,
          f"round={s2.round} sub={s2.sub_round}")

def test_admin_only_creates_subround():
    """Only ADMIN set command → sub_round increments, round stays same."""
    s, islands = simple_state(["1","2"])
    s2, log, _, _ = run_round(s, {"ADMIN": f"set({islands[0]}, 1:600)"})
    check("admin_only_subround",  s2.round == 1 and s2.sub_round == 1,
          f"round={s2.round} sub={s2.sub_round}")

def test_admin_only_consecutive():
    """Two consecutive admin-only rounds → sub_round 1 then 2."""
    s, islands = simple_state(["1","2"])
    s2, _, _, _ = run_round(s, {"ADMIN": f"set({islands[0]}, 1:600)"})
    s3, _, _, _ = run_round(s2, {"ADMIN": f"set({islands[0]}, 1:700)"})
    check("admin_only_consecutive", s3.round == 1 and s3.sub_round == 2,
          f"round={s3.round} sub={s3.sub_round}")

def test_normal_after_admin_resets_subround():
    """Normal round after admin-only rounds → sub_round resets to 0."""
    s, islands = simple_state(["1","2"])
    s2, _, _, _ = run_round(s, {"ADMIN": f"set({islands[0]}, 1:600)"})
    # Now a real move
    s3, _, _, _ = run_round(s2, {"1": f"moving({islands[0]}, {islands[1]}, 100)"})
    check("subround_resets",  s3.round == 2 and s3.sub_round == 0,
          f"round={s3.round} sub={s3.sub_round}")

def test_mixed_admin_and_player_advances():
    """ADMIN + player commands → normal advance, not intermediate."""
    s, islands = simple_state(["1","2"])
    s2, _, _, _ = run_round(s, {
        "ADMIN": f"set({islands[0]}, 1:600)",
        "1":     f"moving({islands[0]}, {islands[1]}, 50)",
    })
    check("mixed_advances", s2.round == 2 and s2.sub_round == 0,
          f"round={s2.round} sub={s2.sub_round}")

def test_invalid_only_does_not_create_subround():
    """Invalid player commands (no valid non-admin) BUT no admin → advances normally."""
    s, islands = simple_state(["1","2"])
    # moving to self is invalid
    s2, _, _, _ = run_round(s, {"1": f"moving({islands[0]}, {islands[0]}, 100)"})
    # only invalid non-admin commands → _has_non_admin_input=True → normal advance
    check("invalid_only_advances", s2.round == 2 and s2.sub_round == 0,
          f"round={s2.round} sub={s2.sub_round}")


# ══════════════════════════════════════════════════════════════════════════════
# 3. Engine — penalty attacks
# ══════════════════════════════════════════════════════════════════════════════

def test_attack_neutral_valid_with_warning():
    """attack on NEUTRAL_ISLAND → valid=True, warning set, troops lost."""
    s, islands = simple_state(["1","2"])
    s.round = 2  # past round 1 restriction
    parsed = parse_commands(f"attack({islands[0]}, {NEUTRAL_ISLAND}, 200)")
    vcmds  = RoundValidator(s).validate_all({"1": parsed})
    vc = vcmds["1"][0]
    check("penalty_neutral_valid",   vc.valid, f"should be valid: {vc.reason}")
    check("penalty_neutral_warning", bool(vc.warning), "should have warning")
    # Execute and check troops are lost
    s2, log, _, _ = run_round(s, {"1": f"attack({islands[0]}, {NEUTRAL_ISLAND}, 200)"})
    remaining = s2.zones[islands[0]].troops.get("1", 0)
    check("penalty_neutral_troops_lost", remaining == 300,
          f"expected 300, got {remaining}")

def test_attack_resource_round1_invalid():
    """attack on resource point in round 1 → invalid."""
    rp = list(RESOURCE_POINTS)[0]
    s, islands = simple_state(["1","2"])
    s.round = 1
    parsed = parse_commands(f"attack({islands[0]}, {rp}, 100)")
    vcmds  = RoundValidator(s).validate_all({"1": parsed})
    vc = vcmds["1"][0]
    check("penalty_rp_round1_invalid", not vc.valid,
          f"should be invalid in round 1")

def test_attack_resource_round2_valid_with_warning():
    """attack on resource point in round 2 → valid, warning, troops lost."""
    rp = list(RESOURCE_POINTS)[0]
    s, islands = simple_state(["1","2"])
    s.round = 2
    parsed = parse_commands(f"attack({islands[0]}, {rp}, 150)")
    vcmds  = RoundValidator(s).validate_all({"1": parsed})
    vc = vcmds["1"][0]
    check("penalty_rp_round2_valid",   vc.valid, f"should be valid: {vc.reason}")
    check("penalty_rp_round2_warning", bool(vc.warning))

def test_moving_resource_round1_invalid():
    """moving to resource point in round 1 → invalid."""
    rp = list(RESOURCE_POINTS)[0]
    s, islands = simple_state(["1","2"])
    s.round = 1
    parsed = parse_commands(f"moving({islands[0]}, {rp}, 100)")
    vcmds  = RoundValidator(s).validate_all({"1": parsed})
    vc = vcmds["1"][0]
    check("penalty_move_rp_round1", not vc.valid)

def test_moving_resource_round2_valid():
    """moving to resource point in round 2+ → valid (no penalty)."""
    rp = list(RESOURCE_POINTS)[0]
    s, islands = simple_state(["1","2"])
    s.round = 2
    parsed = parse_commands(f"moving({islands[0]}, {rp}, 100)")
    vcmds  = RoundValidator(s).validate_all({"1": parsed})
    vc = vcmds["1"][0]
    check("move_rp_round2_valid", vc.valid, f"reason: {vc.reason}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Engine — tie-breaking
# ══════════════════════════════════════════════════════════════════════════════

def _state_for_battle(attacker_troops: dict, defender_troops: dict, target="龍族火山"):
    """Build state for a battle at `target`."""
    all_teams = list(attacker_troops.keys()) + list(defender_troops.keys())
    s = GameState(teams=all_teams, max_rounds=3)
    s.round = 2; s.phase = "input"
    # Give each attacker their own source island
    islands = [z for z in ALL_ZONES if z not in RESOURCE_POINTS
               and z != NEUTRAL_ISLAND and z != target]
    for i, t in enumerate(attacker_troops):
        s.zones[islands[i]] = ZoneState(troops={t: 1000})
    s.zones[target] = ZoneState(troops=defender_troops)
    return s, islands

def test_defender_wins_tie():
    """Attacker and defender have equal troops → defender wins."""
    s, islands = _state_for_battle({"1": {}}, {"2": 300})
    s.zones[islands[0]].troops["1"] = 1000
    cmds = {"1": f"attack({islands[0]}, 龍族火山, 300)"}
    s2, log, _, _ = run_round(s, cmds)
    owner = s2.zones["龍族火山"].owner()
    check("defender_wins_tie", owner == "2",
          f"owner={owner}, troops={s2.zones['龍族火山'].troops}")

def test_larger_force_wins():
    """Attacker with more troops wins."""
    s, islands = _state_for_battle({"1": {}}, {"2": 100})
    s.zones[islands[0]].troops["1"] = 1000
    cmds = {"1": f"attack({islands[0]}, 龍族火山, 400)"}
    s2, log, _, _ = run_round(s, cmds)
    owner = s2.zones["龍族火山"].owner()
    check("attacker_wins", owner == "1", f"owner={owner}")

def test_mutual_elimination():
    """Two solo attackers equal troops, no defender → mutual elimination, zone empty."""
    all_teams = ["1","2"]
    s = GameState(teams=all_teams, max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["精靈森域"] = ZoneState(troops={"2": 1000})
    s.zones["龍族火山"] = ZoneState(troops={})
    cmds = {
        "1": "attack(人類王國, 龍族火山, 300)",
        "2": "attack(精靈森域, 龍族火山, 300)",
    }
    s2, log, _, _ = run_round(s, cmds)
    owner = s2.zones["龍族火山"].owner()
    check("mutual_elim_no_owner", owner is None, f"expected None, got {owner}")
    check("mutual_elim_no_troops",
          s2.zones["龍族火山"].total() == 0,
          f"troops={s2.zones['龍族火山'].troops}")

def test_bonus_20pct():
    """Winner gets 20% of loser troops as bonus."""
    all_teams = ["1","2"]
    s = GameState(teams=all_teams, max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"] = ZoneState(troops={"2": 50})
    cmds = {"1": "attack(人類王國, 龍族火山, 500)"}
    s2, log, _, _ = run_round(s, cmds)
    # loser = defender(50) → bonus = floor(50*0.2) = 10
    winner_troops = s2.zones["龍族火山"].troops.get("1", 0)
    expected = 500 + math.floor(50 * 0.20)
    check("bonus_20pct", winner_troops == expected,
          f"expected {expected}, got {winner_troops}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. Engine — garrison betrayal
# ══════════════════════════════════════════════════════════════════════════════

def test_garrison_betrayal_winner_gets_nac():
    """Attacker wins, had garrison n_Ac in ENEMY zone → n_Ac returned in full.
    Team 1 has 100 garrison at 龍族火山 which team 2 owns (300 troops).
    Team 1 attacks with 400 → wins. Bonus = floor(300*0.2)=60. n_Ac=100 returned.
    """
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    # Team 2 owns 龍族火山 (300 > 100); team 1 has 100 garrison there
    s.zones["龍族火山"] = ZoneState(troops={"1": 100, "2": 300})
    cmds = {"1": "attack(人類王國, 龍族火山, 400)"}
    s2, log, _, _ = run_round(s, cmds)
    t1 = s2.zones["龍族火山"].troops.get("1", 0)
    expected = 400 + math.floor(300 * 0.20) + 100
    check("garrison_winner_nac_returned", t1 == expected,
          f"expected {expected}, got {t1}")

def test_garrison_betrayal_loser_nac_to_pool():
    """Attacker loses, had garrison → n_Ac combined into loser pool.
    Team 1 has 50 garrison at 龍族火山 (team 2 owns with 300).
    Team 1 attacks with 10 → loses.
    Combined pool = 10 + 50 = 60 → bonus = floor(60 * 0.20) = 12.
    """
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    # Team 2 owns 龍族火山; team 1 has 50 garrison
    s.zones["龍族火山"] = ZoneState(troops={"1": 50, "2": 300})
    cmds = {"1": "attack(人類王國, 龍族火山, 10)"}
    s2, log, _, _ = run_round(s, cmds)
    t2 = s2.zones["龍族火山"].troops.get("2", 0)
    # Combined pool = 10 (attacker) + 50 (garrison) = 60 → bonus = floor(60 * 0.20) = 12
    expected = 300 + math.floor((10 + 50) * 0.20)
    check("garrison_loser_nac_pool", t2 == expected,
          f"expected {expected}, got {t2}")


def test_combined_garrison_pool_differs_from_separate():
    """Verify combined pool gives higher bonus than separate calculation.
    Team 1 has 2 garrison; attacks with 3 → loses.
    Separate: floor(3*0.2)+floor(2*0.2) = 0+0 = 0.
    Combined: floor((3+2)*0.2) = floor(1.0) = 1.
    """
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    # Team 2 owns 龍族火山 with 100; team 1 has 2 garrison
    s.zones["龍族火山"] = ZoneState(troops={"1": 2, "2": 100})
    cmds = {"1": "attack(人類王國, 龍族火山, 3)"}
    s2, log, _, _ = run_round(s, cmds)
    t2 = s2.zones["龍族火山"].troops.get("2", 0)
    # Combined: floor((3+2)*0.2) = 1 → 100 + 1 = 101
    expected = 100 + math.floor((3 + 2) * 0.20)
    separate = 100 + math.floor(3 * 0.20) + math.floor(2 * 0.20)
    check("combined_pool_higher_than_separate",
          expected != separate,  # verify the test actually distinguishes the two
          "test values should differ between methods")
    check("combined_garrison_pool", t2 == expected,
          f"expected {expected} (combined), got {t2} (separate would be {separate})")


# ══════════════════════════════════════════════════════════════════════════════
# 5b. Engine — n > troops triggers conflict penalty
# ══════════════════════════════════════════════════════════════════════════════

def test_n_exceeds_troops_triggers_conflict():
    """attack/moving with n > available troops triggers conflict penalty.
    Team 1 has 500 at 人類王國, attacks 精靈森域 with 600 (> 500).
    Expected: all 500 troops moved to neutral island.
    """
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    cmds = {"1": "attack(人類王國, 精靈森域, 600)"}
    s2, log, _, _ = run_round(s, cmds)
    t1_source = s2.zones["人類王國"].troops.get("1", 0)
    t1_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    check("conflict_n_exceeds_source_empty", t1_source == 0,
          f"expected 0 at source, got {t1_source}")
    check("conflict_n_exceeds_neutral", t1_neutral == 500,
          f"expected 500 at neutral (no ×1.5), got {t1_neutral}")
    has_conflict = any("衝突懲罰" in l for l in log)
    check("conflict_n_exceeds_log", has_conflict, f"no conflict log found")


def test_conflict_penalty_skips_neutral_1_5x():
    """Team with conflict penalty: troops moved to neutral island, no ×1.5 applied."""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    cmds = {"1": "attack(人類王國, 精靈森域, 600)"}
    s2, log, _, _ = run_round(s, cmds)
    t1_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    # Without penalty skip: floor(500 * 1.5) = 750; with skip: 500
    check("conflict_no_1_5x", t1_neutral == 500,
          f"expected 500 (no ×1.5), got {t1_neutral} (would be 750 without skip)")
    has_skip = any("跳過" in l and "×1.5" in l for l in log)
    check("conflict_skip_logged", has_skip, f"no skip-log found: {[l for l in log if '中立' in l]}")


def test_zero_troop_owner_wins_as_nominal_defender():
    """Round-start 領主 (0 troops after moving away) remains nominal defender.
    Teams 1+3 both attack with equal force → mutual elimination → team 2 wins.
    Team 2's zone remains empty (no troops), but neither attacker takes it.
    """
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["龍族火山"] = ZoneState(troops={"2": 100})  # team 2 owns at round start
    s.zones["精靈森域"] = ZoneState(troops={"3": 500})
    # Team 2 moves all away; teams 1 and 3 attack with equal force
    cmds = {
        "2": "moving(龍族火山, 中立小島, 100)",
        "1": "attack(人類王國, 龍族火山, 200)",
        "3": "attack(精靈森域, 龍族火山, 200)",
    }
    s2, log, anim, _ = run_round(s, cmds)
    t1_zone = s2.zones["龍族火山"].troops.get("1", 0)
    t3_zone = s2.zones["龍族火山"].troops.get("3", 0)
    # Neither attacker should hold the zone
    check("zero_defender_t1_no_zone", t1_zone == 0,
          f"team 1 should not hold zone, got {t1_zone}")
    check("zero_defender_t3_no_zone", t3_zone == 0,
          f"team 3 should not hold zone, got {t3_zone}")
    # 同歸於盡 in log (mutual elimination of team 1 and 3)
    has_mutual = any("同歸於盡" in l for l in log)
    check("zero_defender_mutual_elim", has_mutual,
          f"expected 同歸於盡: {[l for l in log if '戰鬥' in l or '同歸' in l]}")
    # Battle anim shows team 2 as winner
    battle_evts = [e for e in anim if e.get("type") == "battle" and e.get("zone") == "龍族火山"]
    check("zero_defender_anim_exists", len(battle_evts) > 0, "no battle anim for 龍族火山")
    if battle_evts:
        check("zero_defender_winner_is_2", "2" in battle_evts[0]["winner_teams"],
              f"expected team 2 as winner, got {battle_evts[0]['winner_teams']}")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Engine — set command (forced_owner)
# ══════════════════════════════════════════════════════════════════════════════

def test_set_updates_troops():
    """set command updates zone troops correctly."""
    s, islands = simple_state(["1","2"])
    s2, _, _, _ = run_round(s, {"ADMIN": f"set({islands[0]}, 1:200, 2:300)"})
    z = s2.zones[islands[0]]
    check("set_troops_1", z.troops.get("1", 0) == 200)
    check("set_troops_2", z.troops.get("2", 0) == 300)

def test_set_with_forced_owner():
    """set(zone, K, ...) sets forced_owner."""
    s, islands = simple_state(["1","2"])
    s2, _, _, _ = run_round(s, {"ADMIN": f"set({islands[0]}, 2, 1:300, 2:100)"})
    z = s2.zones[islands[0]]
    check("set_forced_owner", z.forced_owner == "2",
          f"forced_owner={z.forced_owner}")

def test_set_clear_forced_owner():
    """set(zone, 0, ...) clears forced_owner."""
    s, islands = simple_state(["1","2"])
    # First set a forced_owner
    s.zones[islands[0]].forced_owner = "1"
    s2, _, _, _ = run_round(s, {"ADMIN": f"set({islands[0]}, 0, 1:300)"})
    z = s2.zones[islands[0]]
    check("set_clear_fo", z.forced_owner is None,
          f"forced_owner should be None, got {z.forced_owner}")

def test_set_no_k_preserves_forced_owner():
    """set(zone, T:n) without K → forced_owner unchanged."""
    s, islands = simple_state(["1","2"])
    s.zones[islands[0]].forced_owner = "1"
    s2, _, _, _ = run_round(s, {"ADMIN": f"set({islands[0]}, 1:999)"})
    z = s2.zones[islands[0]]
    check("set_no_k_preserves_fo", z.forced_owner == "1",
          f"forced_owner={z.forced_owner}")


# ══════════════════════════════════════════════════════════════════════════════
# 7. Engine — neutral island phase
# ══════════════════════════════════════════════════════════════════════════════

def test_neutral_island_multiplies():
    """Troops on neutral island multiply by 1.5 each round."""
    s, islands = simple_state(["1","2"])
    s.zones[NEUTRAL_ISLAND] = ZoneState(troops={"1": 100})
    s2, log, _, _ = run_round(s, {})
    t = s2.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    expected = math.floor(100 * 1.5)
    check("neutral_1_5x", t == expected, f"expected {expected}, got {t}")

def test_neutral_island_rescue():
    """Team with 0 total troops gets 1000 troops on neutral island."""
    s, islands = simple_state(["1","2"])
    # Team 2 has no troops anywhere
    for z in s.zones.values():
        z.troops.pop("2", None)
    s2, log, _, _ = run_round(s, {})
    rescued = s2.zones[NEUTRAL_ISLAND].troops.get("2", 0)
    check("neutral_rescue", rescued == 1000,
          f"expected 1000, got {rescued}")


# ══════════════════════════════════════════════════════════════════════════════
# 8. Engine — resource points unlocked at round 2
# ══════════════════════════════════════════════════════════════════════════════

def test_resource_points_locked_round1():
    """Resource points give no bonus in round 1."""
    s, islands = simple_state(["1","2"])
    s.round = 1
    rp = list(RESOURCE_POINTS)[0]
    s.zones[rp] = ZoneState(troops={"1": 500})
    s2, log, _, _ = run_round(s, {})
    rp_log = [l for l in log if "資源點" in l or "迷霧" in l or "金錢" in l or "漩渦" in l]
    check("rp_locked_round1", len(rp_log) == 0,
          f"unexpected resource log: {rp_log}")

def test_resource_points_active_round2():
    """Resource points give bonus from round 2."""
    s, islands = simple_state(["1","2"])
    s.round = 2
    rp = list(RESOURCE_POINTS)[0]
    s.zones[rp] = ZoneState(troops={"1": 500})
    before_np = s.national_power.get("1", 0)
    s2, log, _, _ = run_round(s, {})
    # Something in log about resource point
    rp_activity = any(rp in l or "資源" in l for l in log)
    check("rp_active_round2", rp_activity, f"log: {log[:5]}")


# ══════════════════════════════════════════════════════════════════════════════
# 9. app.py Flask integration
# ══════════════════════════════════════════════════════════════════════════════

def test_flask_setup_and_execute():
    """Full cycle: setup → submit → execute → verify state."""
    import importlib
    import app as flask_app
    # Reload to reset global state
    importlib.reload(flask_app)
    client = flask_app.app.test_client()

    # Setup
    r = client.post('/api/setup', json={
        "teams": ["1","2"],
        "max_rounds": 3,
        "territories": {"人類王國": {"1": 500}, "精靈森域": {"2": 300}},
    })
    assert r.status_code == 200, r.get_data()
    d = r.get_json()
    check("flask_setup_ok", d["ok"])

    # Submit commands
    r = client.post('/api/commands/1', json={"text": "moving(HK, ELF, 100)"})
    check("flask_submit_ok", r.get_json()["ok"])

    # Execute
    r = client.post('/api/execute')
    d = r.get_json()
    check("flask_execute_ok",    d["ok"])
    check("flask_round_advanced", d["state"]["round"] == 2)

def test_flask_undo_redo_no_skip():
    """Undo/redo step through sub-rounds one at a time."""
    import importlib
    import app as flask_app
    importlib.reload(flask_app)
    client = flask_app.app.test_client()

    client.post('/api/setup', json={
        "teams": ["1","2"],
        "max_rounds": 3,
        "territories": {"人類王國": {"1": 500}, "精靈森域": {"2": 300}},
    })

    # Admin-only execute → creates sub_round=1
    client.post('/api/commands/ADMIN', json={"text": "set(HK, 1:600)"})
    r = client.post('/api/execute')
    d = r.get_json()
    check("flask_subround_created", d["state"]["sub_round"] == 1,
          f"sub_round={d['state']['sub_round']}")

    # Undo → goes back to sub_round=0, round=1
    r = client.post('/api/undo')
    d = r.get_json()
    check("flask_undo_to_subround0",
          d["state"]["round"] == 1 and d["state"]["sub_round"] == 0,
          f"round={d['state']['round']} sub={d['state']['sub_round']}")

    # Redo → goes to sub_round=1 again (no skipping)
    r = client.post('/api/redo')
    d = r.get_json()
    check("flask_redo_to_subround1",
          d["state"]["round"] == 1 and d["state"]["sub_round"] == 1,
          f"round={d['state']['round']} sub={d['state']['sub_round']}")

def test_flask_admin_accumulate():
    """Multiple ADMIN submits accumulate (not replace)."""
    import importlib
    import app as flask_app
    importlib.reload(flask_app)
    client = flask_app.app.test_client()

    client.post('/api/setup', json={
        "teams": ["1","2"],
        "max_rounds": 3,
        "territories": {"人類王國": {"1": 500}},
    })

    client.post('/api/commands/ADMIN', json={"text": "set(HK, 1:600)"})
    client.post('/api/commands/ADMIN', json={"text": "set(ELF, 2:400)"})

    r = client.get('/api/state')
    d = r.get_json()
    admin_cmds = d["validated_commands"].get("ADMIN", [])
    check("flask_admin_accumulate", len(admin_cmds) == 2,
          f"expected 2 ADMIN cmds, got {len(admin_cmds)}: {admin_cmds}")


# ══════════════════════════════════════════════════════════════════════════════
# 10. State — to_dict includes forced_owner
# ══════════════════════════════════════════════════════════════════════════════

def test_to_dict_forced_owner():
    """to_dict includes forced_owner field in zone entries."""
    s, islands = simple_state(["1","2"])
    s.zones[islands[0]].forced_owner = "1"
    d = s.to_dict()
    fo = d["zones"][islands[0]]["forced_owner"]
    check("to_dict_fo", fo == "1", f"expected '1', got {fo!r}")

def test_to_dict_forced_owner_none():
    """Zones with no forced_owner have forced_owner: null in dict."""
    s, islands = simple_state(["1","2"])
    d = s.to_dict()
    fo = d["zones"][islands[0]]["forced_owner"]
    check("to_dict_fo_none", fo is None, f"expected None, got {fo!r}")


# ══════════════════════════════════════════════════════════════════════════════
# Run
# ══════════════════════════════════════════════════════════════════════════════

ALL_TESTS = [
    # Parser
    test_parser_set_clear,
    test_parser_set_troops_only,
    test_parser_set_with_owner,
    test_parser_set_clear_owner,
    test_parser_set_bad_zone,
    test_parser_set_bad_owner,
    # Admin-only detection
    test_empty_round_advances,
    test_admin_only_creates_subround,
    test_admin_only_consecutive,
    test_normal_after_admin_resets_subround,
    test_mixed_admin_and_player_advances,
    test_invalid_only_does_not_create_subround,
    # Penalty attacks
    test_attack_neutral_valid_with_warning,
    test_attack_resource_round1_invalid,
    test_attack_resource_round2_valid_with_warning,
    test_moving_resource_round1_invalid,
    test_moving_resource_round2_valid,
    # Tie-breaking
    test_defender_wins_tie,
    test_larger_force_wins,
    test_mutual_elimination,
    test_bonus_20pct,
    # Garrison betrayal
    test_garrison_betrayal_winner_gets_nac,
    test_garrison_betrayal_loser_nac_to_pool,
    test_combined_garrison_pool_differs_from_separate,
    # n > troops → conflict
    test_n_exceeds_troops_triggers_conflict,
    test_conflict_penalty_skips_neutral_1_5x,
    # Zero-troop nominal defender
    test_zero_troop_owner_wins_as_nominal_defender,
    # Set command
    test_set_updates_troops,
    test_set_with_forced_owner,
    test_set_clear_forced_owner,
    test_set_no_k_preserves_forced_owner,
    # Neutral island
    test_neutral_island_multiplies,
    test_neutral_island_rescue,
    # Resource points
    test_resource_points_locked_round1,
    test_resource_points_active_round2,
    # Flask integration
    test_flask_setup_and_execute,
    test_flask_undo_redo_no_skip,
    test_flask_admin_accumulate,
    # State serialization
    test_to_dict_forced_owner,
    test_to_dict_forced_owner_none,
]

if __name__ == "__main__":
    for t in ALL_TESTS:
        try:
            t()
        except Exception as e:
            import traceback
            fail(t.__name__, str(e))
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"Results: {PASS}/{PASS+FAIL} PASSED  ({FAIL} FAILED)")
    if FAIL:
        sys.exit(1)
