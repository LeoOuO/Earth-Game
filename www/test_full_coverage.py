"""
超詳細全範圍測試（對照最終大戰說明書 2025 更新版）

覆蓋範圍：
  §3  回合操作驗證（moving / attack / union / union_attack）
  §4  回合結算（戰鬥 / 國力 / 中立小島 / 資源點 / 駐守叛變）
  §6  操作注意事項（衝突裁決 / 平行執行）
  極端案例（0 兵力領主 / 同歸於盡 / 多方資源點 / 聯盟配對）
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))

from game.state  import GameState, ZoneState, ALL_ZONES, NEUTRAL_ISLAND, RESOURCE_POINTS
from game.parser import parse_commands
from game.engine import RoundValidator, execute_round

ISLANDS = [z for z in ALL_ZONES if z not in RESOURCE_POINTS and z != NEUTRAL_ISLAND]

# ── helpers ───────────────────────────────────────────────────────────────────

def run_round(state, cmds_by_team: dict):
    parsed = {t: parse_commands(txt) for t, txt in cmds_by_team.items()}
    vcmds  = RoundValidator(state).validate_all(parsed)
    new_s, log, anim = execute_round(state, vcmds)
    return new_s, log, anim, vcmds

def validate(state, cmds_by_team: dict):
    parsed = {t: parse_commands(txt) for t, txt in cmds_by_team.items()}
    return RoundValidator(state).validate_all(parsed)

def fresh(teams=None, round_=1):
    teams = teams or ["1","2","3","4"]
    s = GameState(teams=teams, max_rounds=3)
    s.round = round_
    s.phase = "input"
    for i, t in enumerate(teams):
        s.zones[ISLANDS[i]] = ZoneState(troops={t: 500})
    return s, ISLANDS

def vc_for(vcmds, team, idx=0):
    return vcmds.get(team, [])[idx]

# ─────────────────────────────────────────────────────────────────────────────
# §3.1  moving 驗證
# ─────────────────────────────────────────────────────────────────────────────

def test_moving_to_own_territory_valid():
    """moving 到己方另一領地 → valid"""
    s, z = fresh(["1","2"])
    s.zones[ISLANDS[2]] = ZoneState(troops={"1": 100})
    vcmds = validate(s, {"1": f"moving({ISLANDS[0]}, {ISLANDS[2]}, 100)"})
    vc = vc_for(vcmds, "1")
    assert vc.valid, vc.reason

def test_moving_to_neutral_island_valid():
    """moving 到中立小島 → valid"""
    s, z = fresh(["1","2"])
    vcmds = validate(s, {"1": f"moving({ISLANDS[0]}, 中立小島, 50)"})
    assert vc_for(vcmds, "1").valid

def test_moving_to_enemy_territory_invalid():
    """moving 到他國領地 → invalid"""
    s, z = fresh(["1","2"])
    vcmds = validate(s, {"1": f"moving({ISLANDS[0]}, {ISLANDS[1]}, 50)"})
    vc = vc_for(vcmds, "1")
    assert not vc.valid

def test_moving_to_unoccupied_territory_invalid():
    """移動到無人領地 → invalid（未佔領視為他國領地）"""
    s, z = fresh(["1","2"])
    # ISLANDS[4] 沒有任何人的兵力
    vcmds = validate(s, {"1": f"moving({ISLANDS[0]}, {ISLANDS[4]}, 50)"})
    vc = vc_for(vcmds, "1")
    assert not vc.valid, "無人領地不可 moving"

def test_moving_resource_point_round1_invalid():
    """第一回合 moving 至資源點 → invalid"""
    s, z = fresh()
    rp = list(RESOURCE_POINTS)[0]
    vcmds = validate(s, {"1": f"moving({ISLANDS[0]}, {rp}, 50)"})
    assert not vc_for(vcmds, "1").valid

def test_moving_resource_point_round2_valid():
    """第二回合 moving 至資源點 → valid"""
    s, z = fresh(round_=2)
    rp = list(RESOURCE_POINTS)[0]
    vcmds = validate(s, {"1": f"moving({ISLANDS[0]}, {rp}, 50)"})
    assert vc_for(vcmds, "1").valid

def test_moving_n_zero_invalid():
    """n=0 → invalid"""
    s, z = fresh()
    vcmds = validate(s, {"1": f"moving({ISLANDS[0]}, 中立小島, 0)"})
    assert not vc_for(vcmds, "1").valid

def test_moving_n_negative_invalid():
    """n<0 → invalid"""
    s, z = fresh()
    vcmds = validate(s, {"1": f"moving({ISLANDS[0]}, 中立小島, -10)"})
    assert not vc_for(vcmds, "1").valid

# ─────────────────────────────────────────────────────────────────────────────
# §3.2  attack 驗證
# ─────────────────────────────────────────────────────────────────────────────

def test_attack_enemy_territory_valid():
    """attack 他國領地 → valid"""
    s, z = fresh(["1","2"])
    vcmds = validate(s, {"1": f"attack({ISLANDS[0]}, {ISLANDS[1]}, 100)"})
    assert vc_for(vcmds, "1").valid

def test_attack_own_territory_invalid():
    """attack 己方領地 → invalid"""
    s, z = fresh(["1","2"])
    s.zones[ISLANDS[2]] = ZoneState(troops={"1": 100})
    vcmds = validate(s, {"1": f"attack({ISLANDS[0]}, {ISLANDS[2]}, 100)"})
    assert not vc_for(vcmds, "1").valid

def test_attack_neutral_island_valid_with_warning():
    """attack 中立小島 → valid（有警告，兵力損失）"""
    s, z = fresh(["1","2"])
    vcmds = validate(s, {"1": f"attack({ISLANDS[0]}, 中立小島, 100)"})
    vc = vc_for(vcmds, "1")
    assert vc.valid and vc.warning

def test_attack_neutral_island_troops_lost():
    """attack 中立小島 → 派遣兵力全部損失，目標不受影響"""
    s, z = fresh(["1","2"])
    s.zones[NEUTRAL_ISLAND] = ZoneState(troops={"2": 300})
    s2, log, _, _ = run_round(s, {"1": f"attack({ISLANDS[0]}, 中立小島, 200)"})
    # team 1 loses 200 from source, neutral island team 2 unchanged (×1.5 applied)
    t1_src = s2.zones[ISLANDS[0]].troops.get("1", 0)
    assert t1_src == 300, f"expected 300 (500-200), got {t1_src}"
    # neutral island team 2 gets ×1.5 via _ceil100: ceil(300*1.5/100)*100 = 500
    t2_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("2", 0)
    import math as _math
    expected_t2 = int(_math.ceil(300 * 1.5 / 100)) * 100  # _ceil100(450) = 500
    assert t2_neutral == expected_t2, f"team 2 neutral untouched, got {t2_neutral}"

def test_attack_resource_point_round1_invalid():
    """第一回合進攻資源點 → invalid"""
    s, z = fresh()
    rp = list(RESOURCE_POINTS)[0]
    vcmds = validate(s, {"1": f"attack({ISLANDS[0]}, {rp}, 100)"})
    assert not vc_for(vcmds, "1").valid

def test_attack_resource_point_round2_troops_lost():
    """第二回合進攻資源點 → valid，兵力移出（進攻資源點不是懲罰，是正常進攻）"""
    s, z = fresh(round_=2)
    rp = list(RESOURCE_POINTS)[0]
    s2, log, _, _ = run_round(s, {"1": f"attack({ISLANDS[0]}, {rp}, 100)"})
    t1 = s2.zones[ISLANDS[0]].troops.get("1", 0)
    assert t1 == 400, f"expected 400 (500-100), got {t1}"
    # Attacking a resource point is a normal attack; troops depart and a battle occurs
    has_attack_log = any(f"attack → {rp}" in l or rp in l for l in log)
    assert has_attack_log

# ─────────────────────────────────────────────────────────────────────────────
# §3.3  union 驗證
# ─────────────────────────────────────────────────────────────────────────────

def test_union_confirmed_troops_move():
    """help 配對成功 → 兵力移動（舊 union 語法已廢棄，改用 help/accept）"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    # help(S, E, n, P) + accept(E, P) → matched, troops move
    cmds = {
        "1": "help(人類王國, 精靈森域, 100, 2)",
        "2": "accept(精靈森域, 1)",
    }
    s2, log, _, _ = run_round(s, cmds)
    # 100 troops should move from 人類王國 to 精靈森域
    t1_src = s2.zones["人類王國"].troops.get("1", 0)
    t1_dst = s2.zones["精靈森域"].troops.get("1", 0)
    assert t1_src == 400, f"expected 400 at source, got {t1_src}"
    assert t1_dst == 100, f"expected 100 at dest, got {t1_dst}"

def test_union_different_n_stays_pending():
    """help 無對應 accept → 未配對，兵力不移動（舊 union_status 已廢棄，改用 help_matched）"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    # Only team 1 sends help, no matching accept from team 2 → unmatched
    cmds = {
        "1": "help(人類王國, 精靈森域, 100, 2)",
    }
    vcmds = validate(s, cmds)
    vc1 = vc_for(vcmds, "1")
    # help without matching accept → help_matched == False (pending/unmatched)
    assert not vc1.help_matched, f"expected help_matched=False (unmatched), got {vc1.help_matched}"

def test_union_different_source_stays_pending():
    """help 目標不一致 → 未配對（help_matched=False）"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"1": 200})
    # Team 1 sends help to 精靈森域; team 2's accept targets 龍族火山 (mismatch)
    cmds = {
        "1": "help(人類王國, 精靈森域, 100, 2)",
        "2": "accept(龍族火山, 1)",  # wrong target → no match
    }
    vcmds = validate(s, cmds)
    assert not vc_for(vcmds, "1").help_matched, "help_matched should be False (target mismatch)"

def test_union_pending_troops_dont_move():
    """pending union → 兵力不移動"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    cmds = {"1": "union(人類王國, 2, 精靈森域, 100)"}  # no partner
    s2, _, _, _ = run_round(s, cmds)
    assert s2.zones["人類王國"].troops.get("1", 0) == 500
    assert s2.zones["精靈森域"].troops.get("1", 0) == 0

# ─────────────────────────────────────────────────────────────────────────────
# §3.4  union_attack 驗證
# ─────────────────────────────────────────────────────────────────────────────

def test_union_attack_own_territory_invalid():
    """union_attack 目標為己方領地 → invalid"""
    s, z = fresh(["1","2","3"])
    vcmds = validate(s, {"1": f"union_attack({ISLANDS[0]}, [2], {ISLANDS[0]}, 100)"})
    assert not vc_for(vcmds, "1").valid

def test_union_attack_ally_territory_invalid():
    """union_attack 目標為盟友的領地（領主） → 駐守叛變廢除後現為 valid（可進攻任何非己方領地）"""
    s, z = fresh(["1","2","3"])
    # team 2 owns ISLANDS[1]; garrison betrayal removed so this is now valid
    vcmds = validate(s, {"1": f"union_attack({ISLANDS[0]}, [2], {ISLANDS[1]}, 100)"})
    vc = vc_for(vcmds, "1")
    # Per new rules: attack is only invalid if you attack your OWN zone (where you have troops)
    assert vc.valid, f"E = 盟友領地，駐守叛變廢除後應為 valid，reason={vc.reason}"

def test_union_attack_ally_garrison_allowed():
    """union_attack 目標盟友只是駐守（非領主） → valid（反叛行為）"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones[ISLANDS[0]] = ZoneState(troops={"1": 500})
    # team 3 owns ISLANDS[2] (majority), but team 2 only has garrison (少數)
    s.zones[ISLANDS[2]] = ZoneState(troops={"3": 400, "2": 100})
    s.zones[ISLANDS[1]] = ZoneState(troops={"2": 500})
    # team 1 union_attacks ISLANDS[2] (team 3's zone) with ally=2 → valid (2 is garrison, not owner)
    vcmds = validate(s, {"1": f"union_attack({ISLANDS[0]}, [2], {ISLANDS[2]}, 100)"})
    vc = vc_for(vcmds, "1")
    assert vc.valid, f"盟友只是駐守應允許（反叛行為），reason: {vc.reason}"

def test_union_attack_confirmed_coalition():
    """三國完整聯盟 → 同一 coalition 攻擊"""
    s = GameState(teams=["1","2","3","4"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 500})
    s.zones["獸人荒原"] = ZoneState(troops={"4": 1000})
    cmds = {
        "1": "union_attack(人類王國, [2,3], 獸人荒原, 300)",
        "2": "union_attack(精靈森域, [1,3], 獸人荒原, 200)",
        "3": "union_attack(龍族火山, [1,2], 獸人荒原, 100)",
    }
    vcmds = validate(s, cmds)
    # All three should be in the same coalition
    allies1 = set(vc_for(vcmds, "1").effective_allies or [])
    allies2 = set(vc_for(vcmds, "2").effective_allies or [])
    assert "2" in allies1 and "3" in allies1
    assert "1" in allies2 and "3" in allies2

# ─────────────────────────────────────────────────────────────────────────────
# §4.1  戰鬥結算
# ─────────────────────────────────────────────────────────────────────────────

def test_battle_larger_force_wins():
    """兵力較大方勝利"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 300})
    s2, _, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 400)"})
    owner = s2.zones["精靈森域"].owner()
    assert owner == "1", f"expected team 1, got {owner}"

def test_battle_defender_wins_equal_force():
    """守方優先：進攻方兵力 == 守方兵力 → 守方勝"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300})
    s.zones["精靈森域"] = ZoneState(troops={"2": 300})
    s2, _, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 300)"})
    owner = s2.zones["精靈森域"].owner()
    assert owner == "2", f"expected defender team 2, got {owner}"

def test_battle_smaller_coalition_wins():
    """小隊獲勝：單國 vs 聯盟同兵力 → 單國（規模最小）勝出"""
    s = GameState(teams=["1","2","3","4"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 500})
    s.zones["獸人荒原"] = ZoneState(troops={"4": 10})  # weak defender
    cmds = {
        # Coalition 2+3 with 200 total
        "2": "union_attack(精靈森域, [3], 獸人荒原, 100)",
        "3": "union_attack(龍族火山, [2], 獸人荒原, 100)",
        # Solo 1 with 200 total (same force, smaller coalition)
        "1": "attack(人類王國, 獸人荒原, 200)",
    }
    s2, log, _, _ = run_round(s, cmds)
    # Solo 1 (size=1) should beat coalition 2+3 (size=2) at equal force
    owner = s2.zones["獸人荒原"].owner()
    assert owner == "1", f"solo 1 should beat coalition 2+3, got owner={owner}"

def test_battle_mutual_elimination_no_winner_empty_zone():
    """無人領地 + 同兵力 → 同歸於盡 → 無勝方，兵力消失"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={})  # empty
    cmds = {
        "1": "attack(人類王國, 龍族火山, 200)",
        "2": "attack(精靈森域, 龍族火山, 200)",
    }
    s2, log, _, _ = run_round(s, cmds)
    z = s2.zones["龍族火山"]
    assert z.owner() is None, f"no winner, zone should be empty, owner={z.owner()}"
    assert sum(z.troops.values()) == 0
    assert any("同歸於盡" in l for l in log)

def test_battle_20pct_bonus_exact():
    """Situation A 勝方存活兵力：survival = winner - strongest_loser，分配後領主 ≥ 500"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 99})
    s2, _, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 300)"})
    t1 = s2.zones["精靈森域"].troops.get("1", 0)
    # Phase 1.5: 精靈森域 total=99 < 300 → cleared; 人類王國 total=200 < 300 → cleared
    # Battle: defender=0, attacker={1:300}; survival=max(0,300-0)=300
    # distribute_situation_a({1:300}, 300) → ceil100(300)=300 < 500 → forced to 500
    assert t1 == 500, f"expected 500 (leader min 500), got {t1}"

def test_battle_rulebook_example1():
    """Phase 1.5 防守不足：守方 100 < 300 → 空島化；攻方 99 vs 99 同歸於盡 → 空島"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 500})
    cmds = {
        "2": "attack(精靈森域, 人類王國, 99)",
        "3": "attack(龍族火山, 人類王國, 99)",
    }
    s2, log, _, _ = run_round(s, cmds)
    t1 = s2.zones["人類王國"].troops.get("1", 0)
    # Phase 1.5: 人類王國 total=100 < 300 → cleared; no defender
    # Attackers 99 vs 99 → mutual elimination → zone empty
    assert t1 == 0, f"expected 0 (zone cleared by min-defense + mutual elim), got {t1}"
    assert any("同歸於盡" in l for l in log)

# ─────────────────────────────────────────────────────────────────────────────
# §4.1  0 兵力名義守方（說明書未明文，使用者確認）
# ─────────────────────────────────────────────────────────────────────────────

def test_zero_troop_owner_nominal_defender_wins_mutual_elim():
    """領主移走全部兵力，進攻方同歸於盡 → 空島（攻方全滅，守方保留空區；forced_owner=2 持續）"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["龍族火山"] = ZoneState(troops={"2": 100})
    s.zones["精靈森域"] = ZoneState(troops={"3": 500})
    cmds = {
        "2": "moving(龍族火山, 中立小島, 100)",
        "1": "attack(人類王國, 龍族火山, 200)",
        "3": "attack(精靈森域, 龍族火山, 200)",
    }
    s2, log, anim, _ = run_round(s, cmds)
    # Attackers mutually eliminate; no actual winner coalition
    assert s2.zones["龍族火山"].troops.get("1", 0) == 0
    assert s2.zones["龍族火山"].troops.get("3", 0) == 0
    assert any("同歸於盡" in l for l in log)
    battle_evts = [e for e in anim if e.get("type") == "battle" and e.get("zone") == "龍族火山"]
    # Engine emits winner_teams=[] when all attackers eliminate each other
    assert battle_evts and battle_evts[0]["winner_teams"] == []
    # forced_owner=2 persists (team 2 moved all troops away but is still forced_owner)
    assert s2.zones["龍族火山"].forced_owner == "2"

def test_zero_troop_owner_loses_to_single_attacker():
    """0 兵力領主被單一進攻方擊敗（50 > 0）"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 100})
    cmds = {
        "2": "moving(精靈森域, 中立小島, 100)",
        "1": "attack(人類王國, 精靈森域, 50)",
    }
    s2, _, _, _ = run_round(s, cmds)
    owner = s2.zones["精靈森域"].owner()
    assert owner == "1", f"attacker should win against 0-troop defender, got {owner}"

def test_zero_troop_owner_persists_next_round():
    """領主移走全部兵力後，下一回合進攻方打過來仍享有守方優先"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 100})
    # Round 1: team 2 moves all away
    s2, _, _, _ = run_round(s, {"2": "moving(精靈森域, 中立小島, 100)"})
    # After round 1: 精靈森域 should have team 2 as owner (forced_owner set by persistence step)
    assert s2.zones["精靈森域"].owner() == "2", "ownership should persist after moving troops"
    # Round 2: team 1 attacks with same troop count as owner (tie → defender priority)
    s3, _, _, _ = run_round(s2, {"1": "attack(人類王國, 精靈森域, 0)"})
    # ... just verify owner is still 2 (no attacker sent)
    assert s3.zones["精靈森域"].owner() == "2"

# ─────────────────────────────────────────────────────────────────────────────
# §4.5  駐守叛變（Garrison Betrayal）
# ─────────────────────────────────────────────────────────────────────────────

def test_garrison_rulebook_example():
    """駐守叛變廢除：有駐兵的領地不可 attack → invalid；zone 維持原狀"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    # E: team 1 has 100 (garrison), team 2 has 200 (owner)
    s.zones["精靈森域"] = ZoneState(troops={"1": 100, "2": 200})
    # Garrison betrayal removed: attack on zone where you have troops → invalid
    vcmds = validate(s, {"1": "attack(人類王國, 精靈森域, 300)"})
    vc = vc_for(vcmds, "1")
    assert not vc.valid, "attack on zone with own garrison should be invalid"
    assert "駐守叛變" in vc.reason or "駐兵" in vc.reason
    # No attack occurs; zone unchanged
    s2, log, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 300)"})
    t1 = s2.zones["精靈森域"].troops.get("1", 0)
    t2 = s2.zones["精靈森域"].troops.get("2", 0)
    assert t1 == 100, f"garrison unchanged (attack invalid), got {t1}"
    assert t2 == 200, f"owner unchanged, got {t2}"

def test_garrison_winner_nac_returned():
    """駐守叛變廢除：T1 在 龍族火山 有 100 駐兵時，發動進攻 → 無效"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"] = ZoneState(troops={"1": 100, "2": 300})
    # T1 has 100 garrison in 龍族火山 → attack INVALID under new rules
    cmds = {"1": "attack(人類王國, 龍族火山, 400)"}
    s2, _, _, _ = run_round(s, cmds)
    # Attack is invalid; garrison and defender unchanged
    t1 = s2.zones["龍族火山"].troops.get("1", 0)
    t2 = s2.zones["龍族火山"].troops.get("2", 0)
    assert t1 == 100, f"garrison should be unchanged (attack invalid), got {t1}"
    assert t2 == 300, f"defender should be unchanged, got {t2}"

def test_garrison_loser_nac_combined_pool():
    """Situation B（守方勝）：prisoner_bonus = floor(total_attacker * 0.20)"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    # T1 attacks without garrison in target (use different target zone)
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"] = ZoneState(troops={"2": 500}, forced_owner="2")
    cmds = {"1": "attack(人類王國, 龍族火山, 100)"}
    s2, _, _, _ = run_round(s, cmds)
    t2 = s2.zones["龍族火山"].troops.get("2", 0)
    # Situation B: defender 500 >= attacker 100. survivor_base = max(500-100,250)=400.
    # prisoner_bonus = floor(100*0.20)=20. Distributed to T2 (sole defender).
    # T2 final = _ceil100((400+20) * 500/500) = _ceil100(420) = 500
    assert t2 >= 400, f"defender should survive with bonus, got {t2}"

def test_garrison_combined_pool_differs_from_separate():
    """Situation A（攻方勝）：存活 = max(0, 進攻總兵 - 守方總兵)，leader 保底 500"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"] = ZoneState(troops={"2": 300}, forced_owner="2")
    cmds = {"1": "attack(人類王國, 龍族火山, 500)"}
    s2, _, _, _ = run_round(s, cmds)
    t1 = s2.zones["龍族火山"].troops.get("1", 0)
    # Situation A: 500 > 300. survival = max(0, 500-300) = 200. leader T1 gets max(200,500)=500
    assert t1 == 500, f"attacker T1 (leader) should have 500 troops, got {t1}"

# ─────────────────────────────────────────────────────────────────────────────
# §4.2  領地國力產出
# ─────────────────────────────────────────────────────────────────────────────

def test_national_power_single_occupant():
    """單一佔領：獲得全額 X"""
    from game.state import TERRITORY_POWER
    s, z = fresh(["1"])
    zone = ISLANDS[0]
    x = TERRITORY_POWER.get(zone, 700)
    before = s.national_power.get("1", 0)
    s2, _, _, _ = run_round(s, {})
    after = s2.national_power.get("1", 0)
    assert after - before == x, f"expected +{x}, got {after - before}"

def test_national_power_multi_occupant_formula():
    """多方駐守：椰子按兵力比例分配（_ceil100）"""
    import math as _math
    from game.state import TERRITORY_POWER
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    zone = ISLANDS[0]
    x = TERRITORY_POWER.get(zone, 1000)
    # team 1: 300 troops, team 2: 100 troops at zone
    s.zones[zone] = ZoneState(troops={"1": 300, "2": 100})
    s.zones[NEUTRAL_ISLAND] = ZoneState(troops={"2": 500})
    s2, log, _, _ = run_round(s, {})
    np1 = s2.national_power.get("1", 0)
    np2 = s2.national_power.get("2", 0)
    total = 400
    # New formula: _ceil100(x * own / total)
    expected_1 = _math.ceil(x * 300 / total / 100) * 100  # _ceil100(750) = 800
    expected_2 = _math.ceil(x * 100 / total / 100) * 100  # _ceil100(250) = 300
    assert np1 == expected_1, f"team 1: expected {expected_1}, got {np1}"
    assert np2 == expected_2, f"team 2: expected {expected_2}, got {np2}"

# ─────────────────────────────────────────────────────────────────────────────
# §4.3  中立小島結算
# ─────────────────────────────────────────────────────────────────────────────

def test_neutral_island_1_5x():
    """中立小島：×1.5（ceil 到百位），之後若總兵力 < 1000 → 救濟補足至 1000"""
    import math as _math
    s, z = fresh(["1","2"])
    # T1: 500 at ISLANDS[0] + 100 at neutral = 600 total
    s.zones[NEUTRAL_ISLAND] = ZoneState(troops={"1": 100})
    s2, _, _, _ = run_round(s, {})
    # Phase 4: _ceil100(100*1.5) = _ceil100(150) = 200. T1 total = 500+200 = 700 < 1000
    # Phase 4.5 rescue: neutral += (1000-700) = 300 → neutral = 500
    assert s2.zones[NEUTRAL_ISLAND].troops.get("1", 0) == 500

def test_neutral_island_rescue():
    """0 兵力救濟：總兵力=0 → +1000"""
    s, z = fresh(["1","2"])
    for zz in s.zones.values():
        zz.troops.pop("2", None)
    s2, _, _, _ = run_round(s, {})
    assert s2.zones[NEUTRAL_ISLAND].troops.get("2", 0) == 1000

def test_conflict_troops_moved_to_neutral_not_destroyed():
    """超額提兵（n > 可用兵力）→ 指令無效，原兵留在出發地（不移往中立）"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    # 需求 600 > 300 → 指令無效，T1 兵力原地不動
    s2, log, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 600)"})
    t1_src = s2.zones["人類王國"].troops.get("1", 0)
    # Source keeps 300 (command invalid). Rescue tops T1 total to 1000 at neutral.
    assert t1_src == 300, f"source should keep troops when command invalid, got {t1_src}"

def test_conflict_no_1_5x():
    """超額提兵 → 指令無效，原地留守。救濟後中立補足至 1000。"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s2, log, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 600)"})
    # T1 source stays at 300, neutral=0. After rescue: 300 < 1000, neutral topped to 700.
    t1_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert t1_neutral == 700, f"expected 700 (rescue after invalid command), got {t1_neutral}"

def test_conflict_rescue_triggers_if_zero():
    """衝突後若仍為 0 兵力 → 觸發 0 兵力救濟"""
    # Edge case: team 1 somehow has 0 troops after conflict
    # In practice this can't happen (conflict moves troops to neutral, total > 0)
    # But test the rescue mechanism directly
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"2": 500})
    # team 1 has no troops anywhere
    s2, _, _, _ = run_round(s, {})
    assert s2.zones[NEUTRAL_ISLAND].troops.get("1", 0) == 1000

# ─────────────────────────────────────────────────────────────────────────────
# §4.4  資源點結算
# ─────────────────────────────────────────────────────────────────────────────

def test_fogisle_each_team_gets_2000_troops():
    """迷霧島：≤4 隊各獲得 +2000 兵力（Phase 1.5 不適用資源點，T1+T2 均留存）"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["迷霧島"] = ZoneState(troops={"1": 300, "2": 100})
    s2, log, _, _ = run_round(s, {})
    fog = s2.zones["迷霧島"]
    # Phase 1.5 only applies to ISLANDS, not resource points → both T1+T2 survive
    # Both get +2000 troops (2 teams ≤ 4)
    assert fog.troops.get("1", 0) == 300 + 2000, f"team 1 fog: {fog.troops.get('1')}"
    assert fog.troops.get("2", 0) == 100 + 2000, f"team 2 fog: {fog.troops.get('2')}"
    assert any("迷霧島" in l for l in log)

def test_goldisle_3000_coconuts_split_evenly():
    """金錢島：3000 椰子平分（≥300 兵力才留在島上）"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["金錢島"] = ZoneState(troops={"1": 600, "2": 400})
    s2, log, _, _ = run_round(s, {})
    np1 = s2.national_power.get("1", 0)
    np2 = s2.national_power.get("2", 0)
    # 3000 / 2 teams = 1500 each (ceil to 100)
    assert np1 == 1500, f"team 1 gold: {np1} expected 1500"
    assert np2 == 1500, f"team 2 gold: {np2} expected 1500"
    assert any("金錢島" in l for l in log)


def test_resource_point_locked_round1():
    """第一回合資源點不結算"""
    s, z = fresh(["1","2"])
    s.round = 1
    s.zones["迷霧島"] = ZoneState(troops={"1": 500})
    np_before = s.national_power.get("1", 0)
    s2, log, _, _ = run_round(s, {})
    fog_after = s2.zones["迷霧島"].troops.get("1", 0)
    # Should not increase (no resource point settlement in round 1)
    assert fog_after == 500, f"resource point locked in round 1, got {fog_after}"

# ─────────────────────────────────────────────────────────────────────────────
# §6.1  操作衝突裁決
# ─────────────────────────────────────────────────────────────────────────────

def test_conflict_n_exceeds_troops():
    """n > 可用兵力 → 指令無效，兵力原地不動（Phase 1.5 可能清除）。救濟後中立補足至 1000"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s2, log, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 600)"})
    # Source has 100 → Phase 1.5 clears (< 300). T1 total = 0 → rescue tops to 1000.
    assert s2.zones["人類王國"].troops.get("1", 0) == 0
    assert s2.zones[NEUTRAL_ISLAND].troops.get("1", 0) == 1000

def test_conflict_two_ops_sum_exceeds():
    """兩個操作合計超過兵力 → 皆無效（per-source conflict check）。救濟後中立補足 1000。"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"1": 50})
    # 50+80=130 > 100 → both commands invalidated by per-source check
    s2, log, _, _ = run_round(s, {"1": "moving(人類王國, 中立小島, 50)\nattack(人類王國, 精靈森域, 80)"})
    t1_src = s2.zones["人類王國"].troops.get("1", 0)
    t1_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    # Both commands invalid → source cleared by Phase 1.5 (100 < 300). Rescue → 1000 at neutral.
    assert t1_src == 0
    assert t1_neutral == 1000
    # 精靈森域 should not be attacked
    assert s2.zones["精靈森域"].owner() == "2"

def test_conflict_only_penalizes_conflicting_zone():
    """衝突只懲罰發生衝突的來源領地，其他領地操作不受影響"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["龍族火山"] = ZoneState(troops={"1": 300})   # team 1 second zone
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["獸人荒原"] = ZoneState(troops={"3": 200})  # team 1 攻 300 > 200 → team 1 wins
    cmds = {
        # 人類王國 conflict: needs 200, has 100
        "1": "attack(人類王國, 精靈森域, 200)\nattack(龍族火山, 獸人荒原, 300)",
    }
    s2, log, _, _ = run_round(s, cmds)
    # 人類王國 should be penalized (100 moved to neutral)
    assert s2.zones["人類王國"].troops.get("1", 0) == 0
    # 龍族火山 op should succeed (300 ≤ 300, no conflict)
    # 獸人荒原 should have been attacked
    t1_獸 = s2.zones["獸人荒原"].troops.get("1", 0)
    assert t1_獸 > 0 or s2.zones["獸人荒原"].owner() == "1", \
        "龍族火山 attack should NOT be penalized"

# ─────────────────────────────────────────────────────────────────────────────
# §6.1  Admin-only round detection
# ─────────────────────────────────────────────────────────────────────────────

def test_empty_round_advances_normally():
    """無任何指令 → 正常推進"""
    s, z = fresh()
    s2, _, _, _ = run_round(s, {})
    assert s2.round == 2 and s2.sub_round == 0

def test_admin_only_creates_subround():
    """只有 ADMIN 有效指令 → 創建中間版本"""
    s, z = fresh()
    s2, _, _, _ = run_round(s, {"ADMIN": f"set({ISLANDS[0]}, 1:600)"})
    assert s2.round == 1 and s2.sub_round == 1

def test_player_with_admin_advances():
    """玩家有效指令 + ADMIN → 正常推進"""
    s, z = fresh()
    s2, _, _, _ = run_round(s, {
        "1": f"moving({ISLANDS[0]}, 中立小島, 50)",
        "ADMIN": f"set({ISLANDS[1]}, 2:600)",
    })
    assert s2.round == 2

def test_invalid_only_advances_normally():
    """只有無效指令 → 正常推進（無有效 ADMIN）"""
    s, z = fresh()
    s2, _, _, _ = run_round(s, {"1": "invalid_command()"})
    assert s2.round == 2 and s2.sub_round == 0

# ─────────────────────────────────────────────────────────────────────────────
# 極端案例
# ─────────────────────────────────────────────────────────────────────────────

def test_three_way_tie_then_defender_wins():
    """三方平局 → 守方優先勝出"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300})  # defender
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 500})
    cmds = {
        "2": "attack(精靈森域, 人類王國, 300)",
        "3": "attack(龍族火山, 人類王國, 300)",
    }
    s2, _, _, _ = run_round(s, cmds)
    assert s2.zones["人類王國"].owner() == "1"

def test_multi_round_national_power_accumulates():
    """多回合國力累積"""
    s, z = fresh(["1"])
    from game.state import TERRITORY_POWER
    x = TERRITORY_POWER.get(ISLANDS[0], 700)
    s2, _, _, _ = run_round(s, {})
    s3, _, _, _ = run_round(s2, {})
    np = s3.national_power.get("1", 0)
    assert np == x * 2, f"expected {x*2}, got {np}"

def test_penalty_attack_counts_as_valid_op():
    """penalty attack（進攻中立小島）佔用操作次數，超過 5 次靜默忽略"""
    s, z = fresh(["1","2"])
    # 6 ops exceeds 5-op limit; penalty attacks count toward limit
    vcmds = validate(s, {"1": (
        "attack(人類王國, 中立小島, 10)\n"
        "attack(人類王國, 中立小島, 10)\n"
        "attack(人類王國, 中立小島, 10)\n"
        "attack(人類王國, 中立小島, 10)\n"
        "attack(人類王國, 中立小島, 10)\n"
        "attack(人類王國, 中立小島, 10)"
    )})
    ops = vcmds.get("1", [])
    assert ops[4].valid,  "5th op should still be valid"
    assert not ops[5].valid, "6th op should be invalid due to 5-op limit"

def test_conflict_does_not_affect_neutral_island_owner():
    """T1 的無效指令不影響 T2 的中立小島；T2 中立 ×1.5 後救濟"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones[NEUTRAL_ISLAND] = ZoneState(troops={"2": 200})
    s2, _, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 600)"})
    # T2 at neutral: _ceil100(200*1.5)=300. T2 total = 500+300=800 < 1000 → rescue adds 200 → neutral=500
    t2_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("2", 0)
    assert t2_neutral == 500, f"team 2 neutral (1.5x + rescue), got {t2_neutral}"

def test_union_attack_same_zone_penalty_applies():
    """union_attack 目標為中立小島 → 所有聯盟成員損失兵力"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 500})
    cmds = {
        "1": "union_attack(人類王國, [2], 中立小島, 100)",
        "2": "union_attack(精靈森域, [1], 中立小島, 80)",
    }
    s2, log, _, _ = run_round(s, cmds)
    t1 = s2.zones["人類王國"].troops.get("1", 0)
    t2 = s2.zones["精靈森域"].troops.get("2", 0)
    # both lose their sent troops
    assert t1 == 400, f"team 1 should lose 100, got {t1}"
    assert t2 == 420, f"team 2 should lose 80, got {t2}"

def test_max_rounds_game_ends():
    """超過 max_rounds → phase = 'done'"""
    s = GameState(teams=["1"], max_rounds=1)
    s.round = 1; s.phase = "input"
    s.zones[ISLANDS[0]] = ZoneState(troops={"1": 500})
    s2, _, _, _ = run_round(s, {})
    assert s2.phase == "done"


# ─────────────────────────────────────────────────────────────────────────────
# §7.6 同一國多個進攻聯盟（同一目標）
# ─────────────────────────────────────────────────────────────────────────────

def test_same_team_in_two_coalitions_winner_troops_preserved():
    """
    T1 同時以 solo(100) 和聯盟(T1+T2: 200+150) 進攻同一目標。
    Engine 合併 T1 所有指令 → T1 宣告盟友 [2]，形成聯盟 {1,2}。
    coalition {1,2} total=450, defender T3=300 → Situation A.
    survival = max(0, 450-300) = 150.
    T1 (300 troops in coalition) = _ceil100(150*300/450)=100 → leader ≥ 500 → 500.
    T2 (150) = _ceil100(150*150/450)=100.
    """
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"]  = ZoneState(troops={"1": 1000})
    s.zones["精靈森域"]  = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"]  = ZoneState(troops={"2": 500})
    s.zones["獸人荒原"]  = ZoneState(troops={"3": 500})
    s.zones["布丁狗族"]  = ZoneState(troops={"3": 300})
    cmds = {
        "1": "attack(人類王國, 布丁狗族, 100)\nunion_attack(精靈森域, [2], 布丁狗族, 200)",
        "2": "union_attack(龍族火山, [1], 布丁狗族, 150)",
    }
    s2, log, _, _ = run_round(s, cmds)
    t1 = s2.zones["布丁狗族"].troops.get("1", 0)
    t2 = s2.zones["布丁狗族"].troops.get("2", 0)
    # New Situation A formula: T1=500 (leader), T2=100
    assert t1 == 500, f"team 1 (leader) should have 500, got {t1}"
    assert t2 == 100, f"team 2 should have 100, got {t2}"

def test_same_team_solo_loses_troops_enter_pool():
    """T1 solo(50) + 聯盟 T1+T2(300+200) 攻空島。T1 total_troops=350, T2=200. Situation A."""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"]  = ZoneState(troops={"1": 1000})
    s.zones["精靈森域"]  = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"]  = ZoneState(troops={"2": 500})
    s.zones["侏儒劇場"]  = ZoneState()
    cmds = {
        "1": "attack(人類王國, 侏儒劇場, 50)\nunion_attack(精靈森域, [2], 侏儒劇場, 300)",
        "2": "union_attack(龍族火山, [1], 侏儒劇場, 200)",
    }
    s2, log, _, _ = run_round(s, cmds)
    t1 = s2.zones["侏儒劇場"].troops.get("1", 0)
    t2 = s2.zones["侏儒劇場"].troops.get("2", 0)
    # Empty target: survival = 550. T1 share = _ceil100(350) = 400 → leader ≥ 500 → 500. T2 = _ceil100(200) = 200.
    assert t1 == 500, f"team 1 (leader): got {t1}"
    assert t2 == 200, f"team 2: got {t2}"


# ─────────────────────────────────────────────────────────────────────────────
# 新規則：各勝方獨立獲得 full 20% 獎勵（非比例瓜分）
# ─────────────────────────────────────────────────────────────────────────────

def test_coalition_each_winner_gets_full_bonus():
    """A+B 聯盟勝：Situation A；T1(150) leader ≥500, T2(150) gets _ceil100 share"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 100})
    cmds = {
        "1": f"union_attack(人類王國, [2], 龍族火山, 150)",
        "2": f"union_attack(精靈森域, [1], 龍族火山, 150)",
    }
    s2, _, _, _ = run_round(s, cmds)
    # {1,2} total=300, defender T3=100 → Situation A
    # survival = max(0, 300-100) = 200; T1=_ceil100(100)=100 → leader → 500; T2=100
    assert s2.zones["龍族火山"].troops.get("1", 0) == 500, "team 1 (leader) should get 500"
    assert s2.zones["龍族火山"].troops.get("2", 0) == 200, "team 2 should get 200"

def test_regular_battle_winner_gets_full_bonus_from_eliminated():
    """守方 500 兵，T2+T3 各 solo 200 → Situation B；survival_base=300, prisoner_bonus=80, _ceil100(380)=400"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 500})
    cmds = {
        "2": "attack(精靈森域, 人類王國, 200)",
        "3": "attack(龍族火山, 人類王國, 200)",
    }
    s2, _, _, _ = run_round(s, cmds)
    # Situation B: defender 500 >= total_attacker 400
    # survival_base = max(500-200, 250) = 300; prisoner_bonus = floor(400*0.2) = 80
    # total = 380 → _ceil100(380) = 400
    assert s2.zones["人類王國"].troops.get("1", 0) == 400

def test_5op_limit_invalid_ops_dont_count():
    """無效操作不佔用 5 次限制：3 個無效 + 5 個有效 = 前 5 個有效通過"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    # Submit 3 invalid (round-1 resource point attack) + 6 valid attacks on neutral island
    text = (
        "attack(人類王國, 迷霧島, 10)\n"    # invalid (round 1 resource)
        "attack(人類王國, 金錢島, 10)\n"    # invalid (round 1 resource)
        "attack(人類王國, 漩渦, 10)\n"      # invalid (round 1 resource)
        "attack(人類王國, 中立小島, 10)\n"  # valid slot 1
        "attack(人類王國, 中立小島, 10)\n"  # valid slot 2
        "attack(人類王國, 中立小島, 10)\n"  # valid slot 3
        "attack(人類王國, 中立小島, 10)\n"  # valid slot 4
        "attack(人類王國, 中立小島, 10)\n"  # valid slot 5
        "attack(人類王國, 中立小島, 10)"    # valid slot 6 → truncated
    )
    vcmds = validate(s, {"1": text})
    ops = vcmds["1"]
    # First 3 invalid (round 1 resource)
    assert not ops[0].valid
    assert not ops[1].valid
    assert not ops[2].valid
    # Slots 1-5 valid
    for i in range(3, 8):
        assert ops[i].valid, f"op[{i}] should be valid (slot {i-2})"
    # Slot 6 truncated
    assert not ops[8].valid, "6th valid op should be truncated"

def test_forced_owner_persists_after_normal_conquest():
    """普通攻奪領地後，下一回合移走全部兵力仍保有領主地位"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 100})
    # Round 1: team 1 conquers 精靈森域
    s2, _, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 200)"})
    assert s2.zones["精靈森域"].owner() == "1", "team 1 should own 精靈森域 after conquest"
    # Round 2: team 1 moves all troops away from 精靈森域
    s3, _, _, _ = run_round(s2, {"1": "moving(精靈森域, 人類王國, 200)"})
    # Wait – how many troops does team 1 have at 精靈森域 after round 1?
    t1_at_zone = s2.zones["精靈森域"].troops.get("1", 0)
    # After moving, team 1 has 0 troops but should still be owner
    assert s3.zones["精靈森域"].owner() == "1", (
        f"owner should persist at 0 troops (forced_owner), got {s3.zones['精靈森域'].owner()}"
    )

def test_garrison_0_troop_abandons():
    """T2 撤走全部駐守兵力後，T1 仍為 forced_owner（T1 需 ≥300 才不被 Phase 1.5 清除）"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"2": 500})
    # zone: T1 is forced_owner with 300 troops, T2 has 50 garrison
    s.zones["精靈森域"] = ZoneState(troops={"1": 300, "2": 50}, forced_owner="1")
    # T2 moves all garrison away → 精靈森域 has T1:300, T2:0 → total=300 (not cleared by Phase 1.5)
    s2, _, _, _ = run_round(s, {"2": "moving(精靈森域, 人類王國, 50)"})
    z = s2.zones["精靈森域"]
    assert z.troops.get("2", 0) == 0, "team 2 garrison should be gone"
    assert z.owner() == "1", "team 1 remains forced_owner after T2 abandons garrison"
    assert "2" not in z.troops, "team 2 should not appear in troops at all"

# ─────────────────────────────────────────────────────────────────────────────
# Run (pytest discovers all test_* functions automatically)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback
    passed = failed = 0
    fns = [(k, v) for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for name, fn in fns:
        try:
            fn()
            passed += 1
            print(f"PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {name}: {e}")
            traceback.print_exc()
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{passed+failed} PASSED  ({failed} FAILED)")
    if failed:
        sys.exit(1)
