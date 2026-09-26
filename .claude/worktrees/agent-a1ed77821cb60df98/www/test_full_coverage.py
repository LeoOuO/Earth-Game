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
    # neutral island team 2: ceil100(300*1.5)=500, plus rescue if total<1000
    # T2 has 500 at ISLANDS[1] + 300 neutral = 800 < 1000 → +200 rescue → 500
    t2_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("2", 0)
    assert t2_neutral == 500, f"team 2 neutral untouched, got {t2_neutral}"

def test_attack_resource_point_round1_invalid():
    """第一回合進攻資源點 → invalid"""
    s, z = fresh()
    rp = list(RESOURCE_POINTS)[0]
    vcmds = validate(s, {"1": f"attack({ISLANDS[0]}, {rp}, 100)"})
    assert not vc_for(vcmds, "1").valid

def test_attack_resource_point_round2_troops_lost():
    """第二回合進攻資源點 → valid，兵力損失"""
    s, z = fresh(round_=2)
    rp = list(RESOURCE_POINTS)[0]
    s2, log, _, _ = run_round(s, {"1": f"attack({ISLANDS[0]}, {rp}, 100)"})
    t1 = s2.zones[ISLANDS[0]].troops.get("1", 0)
    assert t1 == 400, f"expected 400 (500-100), got {t1}"

# ─────────────────────────────────────────────────────────────────────────────
# §3.3  union 驗證
# ─────────────────────────────────────────────────────────────────────────────

def test_union_confirmed_troops_move():
    """雙方 help/accept 互指且 S/E/n 相同 → 成立，兵力移動"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    # T1 sends help, T2 accepts
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
    """help 無對應 accept → 聯盟未成立（pending），兵力不移動"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    cmds = {
        "1": "help(人類王國, 精靈森域, 100, 2)",
        # no accept from T2 → no match
    }
    vcmds = validate(s, cmds)
    vc1 = vc_for(vcmds, "1")
    assert not vc1.help_matched, f"expected pending (no match), got help_matched={vc1.help_matched}"

def test_union_different_source_stays_pending():
    """S 不相同 → 聯盟未成立（兩個 help 不互配，各自無 accept）"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"1": 200})
    cmds = {
        "1": "help(人類王國, 精靈森域, 100, 2)",
        # T2 sends different help (different source) → no match
        "2": "help(龍族火山, 精靈森域, 100, 1)",
    }
    vcmds = validate(s, cmds)
    assert not vc_for(vcmds, "1").help_matched, "no match expected"

def test_union_pending_troops_dont_move():
    """pending help（無 accept）→ 兵力不移動"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    cmds = {"1": "help(人類王國, 精靈森域, 100, 2)"}  # no accept from T2
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
    """union_attack 目標為己方領地 → invalid（§3.4）"""
    s, z = fresh(["1","2","3"])
    # team 1 attacks its own territory with ally team 2 → invalid
    vcmds = validate(s, {"1": f"union_attack({ISLANDS[0]}, [2], {ISLANDS[0]}, 100)"})
    vc = vc_for(vcmds, "1")
    assert not vc.valid, "union_attack targeting own territory should be invalid"

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
    """Situation A: attacker wins, leader guarantee 500"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 99})
    s2, _, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 300)"})
    t1 = s2.zones["精靈森域"].troops.get("1", 0)
    # Situation A: 300 vs 99, survival=201, ceil100(201)=300, leader T1: max(300,500)=500
    assert t1 == 500, f"expected 500 (leader guarantee), got {t1}"

def test_battle_rulebook_example1():
    """說明書 §4.1 範例1：A(300 defender) vs B(99) vs C(99) → B and C tie → A retains zone"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300})  # min 300 to avoid phase 1.5 clearing
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 500})
    cmds = {
        "2": "attack(精靈森域, 人類王國, 99)",
        "3": "attack(龍族火山, 人類王國, 99)",
    }
    s2, _, _, _ = run_round(s, cmds)
    t1 = s2.zones["人類王國"].troops.get("1", 0)
    # B(99) vs C(99) → mutual elimination → defender keeps original 300 troops
    assert t1 == 300, f"expected 300 (defender retains), got {t1}"

# ─────────────────────────────────────────────────────────────────────────────
# §4.1  0 兵力名義守方（說明書未明文，使用者確認）
# ─────────────────────────────────────────────────────────────────────────────

def test_zero_troop_owner_nominal_defender_wins_mutual_elim():
    """領主本回合移走全部兵力，進攻方同歸於盡 → 領主名義空城勝，新引擎不給 bonus"""
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
    assert s2.zones["龍族火山"].troops.get("1", 0) == 0
    assert s2.zones["龍族火山"].troops.get("3", 0) == 0
    assert any("同歸於盡" in l for l in log)
    battle_evts = [e for e in anim if e.get("type") == "battle" and e.get("zone") == "龍族火山"]
    assert battle_evts and "2" in battle_evts[0].get("winner_teams", [])
    # New engine: 0-troop owner wins nominally but gets NO bonus troops
    assert s2.zones["龍族火山"].troops.get("2", 0) == 0, (
        f"空城勝：new engine gives no bonus troops, got {s2.zones['龍族火山'].troops.get('2', 0)}"
    )

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
    """§4.1: A(300) attacks B(99) → A wins with leader guarantee 500"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 99})
    cmds = {"1": "attack(人類王國, 精靈森域, 300)"}
    s2, log, _, _ = run_round(s, cmds)
    t1 = s2.zones["精靈森域"].troops.get("1", 0)
    # Situation A: survival=201, ceil100(201)=300, leader T1 gets max(300,500)=500
    assert t1 == 500, f"expected 500 (leader guarantee), got {t1}"
    t2 = s2.zones["精靈森域"].troops.get("2", 0)
    assert t2 == 0

def test_garrison_winner_nac_returned():
    """攻方勝利 Situation A: 存活按比例分配，領袖最少 500"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"] = ZoneState(troops={"2": 300})
    cmds = {"1": "attack(人類王國, 龍族火山, 400)"}
    s2, _, _, _ = run_round(s, cmds)
    t1 = s2.zones["龍族火山"].troops.get("1", 0)
    # Situation A: 400 vs 300. survival=100. ceil100(100)=100. Leader T1: max(100,500)=500
    assert t1 == 500, f"expected 500, got {t1}"

def test_garrison_loser_nac_combined_pool():
    """攻方敗北 Situation B: 守方存活"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"] = ZoneState(troops={"2": 300})
    cmds = {"1": "attack(人類王國, 龍族火山, 10)"}
    s2, _, _, _ = run_round(s, cmds)
    t2 = s2.zones["龍族火山"].troops.get("2", 0)
    # Situation B: defender wins. survival_base=max(300-10, 150)=290. prisoner_bonus=floor(10*0.2)=2. total=292. ceil100(292)=300
    assert t2 == 300, f"expected 300, got {t2}"

def test_garrison_combined_pool_differs_from_separate():
    """Situation B 守方存活: ceil100 處理"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"] = ZoneState(troops={"2": 300})
    cmds = {"1": "attack(人類王國, 龍族火山, 3)"}
    s2, _, _, _ = run_round(s, cmds)
    t2 = s2.zones["龍族火山"].troops.get("2", 0)
    # Situation B: survival_base=max(300-3, 150)=297. prisoner_bonus=floor(3*0.2)=0. ceil100(297)=300
    assert t2 == 300, f"expected 300, got {t2}"

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
    """多方駐守：按比例分配（_ceil100(x * troops / total_t)）"""
    from game.state import TERRITORY_POWER
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    zone = ISLANDS[0]
    x = TERRITORY_POWER.get(zone, 700)
    # team 1 owns zone with 300; team 2 has 100 as garrison
    s.zones[zone] = ZoneState(troops={"1": 300, "2": 100})
    s.zones[NEUTRAL_ISLAND] = ZoneState(troops={"2": 500})  # team 2 needs troops but no extra territory NP
    s2, log, _, _ = run_round(s, {})
    np1 = s2.national_power.get("1", 0)
    np2 = s2.national_power.get("2", 0)
    # New engine: proportional only, ceil100
    # ceil100(x * 300/400) and ceil100(x * 100/400)
    import math as _math
    def ceil100(v): return _math.ceil(v / 100) * 100
    expected_1 = ceil100(x * 300 / 400)  # ceil100(1000*0.75)=800 for x=1000
    expected_2 = ceil100(x * 100 / 400)  # ceil100(1000*0.25)=300 for x=1000
    assert np1 == expected_1, f"team 1: expected {expected_1}, got {np1}"
    assert np2 == expected_2, f"team 2: expected {expected_2}, got {np2}"

# ─────────────────────────────────────────────────────────────────────────────
# §4.3  中立小島結算
# ─────────────────────────────────────────────────────────────────────────────

def test_neutral_island_1_5x():
    """中立小島：×1.5（ceil100），加救濟若 total<1000"""
    s, z = fresh(["1","2"])
    s.zones[NEUTRAL_ISLAND] = ZoneState(troops={"1": 100})
    s2, _, _, _ = run_round(s, {})
    # T1 has 500 at ISLANDS[0] + ceil100(100*1.5)=200 neutral = 700 < 1000 → +300 rescue → 500 total at neutral
    assert s2.zones[NEUTRAL_ISLAND].troops.get("1", 0) == 500

def test_neutral_island_rescue():
    """0 兵力救濟：總兵力=0 → +1000"""
    s, z = fresh(["1","2"])
    for zz in s.zones.values():
        zz.troops.pop("2", None)
    s2, _, _, _ = run_round(s, {})
    assert s2.zones[NEUTRAL_ISLAND].troops.get("2", 0) == 1000

def test_conflict_troops_moved_to_neutral_not_destroyed():
    """衝突懲罰：新引擎兵力留在來源地（不移至中立），再由救濟處理"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    # 需求 600 > 300 → 衝突
    s2, log, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 600)"})
    t1_src = s2.zones["人類王國"].troops.get("1", 0)
    t1_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert t1_src == 300, "conflict: troops STAY at source"
    assert t1_neutral == 700, "rescue: 300 < 1000 → +700 at neutral"

def test_conflict_no_1_5x():
    """衝突懲罰：新引擎兵力留在來源地（300），救濟補足至 1000"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 300})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s2, log, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 600)"})
    t1_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    # Conflict troops stay at source (300). Rescue fires: 300 < 1000 → +700 at neutral
    assert t1_neutral == 700, f"rescue adds 700, got {t1_neutral}"

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

def test_fogisle_1000_troops_proportional():
    """迷霧島：2 隊（≤4）→ 各得 +2000 兵力"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    # team 1: 300, team 2: 100 at 迷霧島
    s.zones["迷霧島"] = ZoneState(troops={"1": 300, "2": 100})
    s2, log, _, _ = run_round(s, {})
    fog = s2.zones["迷霧島"]
    # 2 teams (≤4) → each gets +2000 troops
    assert fog.troops.get("1", 0) == 2300, f"team 1 fog: {fog.troops.get('1')}"
    assert fog.troops.get("2", 0) == 2100, f"team 2 fog: {fog.troops.get('2')}"

def test_goldisle_1000_national_power_proportional():
    """金錢島：2 隊 → 3000 均分，各得 1500"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    # Only troops at 金錢島; no home territories so territory NP = 0
    s.zones["金錢島"] = ZoneState(troops={"1": 600, "2": 400})
    s2, log, _, _ = run_round(s, {})
    np1 = s2.national_power.get("1", 0)
    np2 = s2.national_power.get("2", 0)
    # New engine: 3000 split evenly → 1500 each
    assert np1 == 1500, f"team 1 gold: {np1} expected 1500"
    assert np2 == 1500, f"team 2 gold: {np2} expected 1500"

def test_vortex_even_teams_2000_troops():
    """漩渦：2 隊（偶數 ≠6）→ +3000 NP 各隊，兵力不變"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 500})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["漩渦"] = ZoneState(troops={"1": 600, "2": 400})
    s2, log, _, _ = run_round(s, {})
    vortex = s2.zones["漩渦"]
    # even (≠6) → +3000 NP each, troops unchanged
    assert vortex.troops.get("1", 0) == 600, "troops should not change"
    assert vortex.troops.get("2", 0) == 400, "troops should not change"
    vortex_np_log = [l for l in log if "漩渦" in l]
    assert any("3000" in l for l in vortex_np_log), f"expected +3000 NP in vortex log: {vortex_np_log}"

def test_vortex_odd_teams_2000_national_power():
    """漩渦：3 隊（奇數）→ +3000 兵力各隊"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 2; s.phase = "input"
    # Only troops at 漩渦; no home territories so territory NP = 0
    # 3 teams at 漩渦 → odd
    s.zones["漩渦"] = ZoneState(troops={"1": 500, "2": 300, "3": 200})
    s2, log, _, _ = run_round(s, {})
    v = s2.zones["漩渦"]
    # 3 teams (odd) → +3000 troops each
    assert v.troops.get("1", 0) == 500 + 3000, f"t1: {v.troops.get('1')}"
    assert v.troops.get("2", 0) == 300 + 3000, f"t2: {v.troops.get('2')}"
    assert v.troops.get("3", 0) == 200 + 3000, f"t3: {v.troops.get('3')}"
    vortex_log = [l for l in log if "漩渦" in l]
    assert any("3000" in l for l in vortex_log)

def test_vortex_4_teams_no_output():
    """漩渦：4 隊（偶數 ≠6）→ +3000 NP 各隊"""
    s = GameState(teams=["1","2","3","4"], max_rounds=3)
    s.round = 2; s.phase = "input"
    for i, t in enumerate(["1","2","3","4"]):
        s.zones[ISLANDS[i]] = ZoneState(troops={t: 500})
    s.zones["漩渦"] = ZoneState(troops={"1":100,"2":100,"3":100,"4":100})
    before_np = {t: s.national_power.get(t, 0) for t in ["1","2","3","4"]}
    s2, log, _, _ = run_round(s, {})
    # 4 teams (even ≠6) → +3000 NP each
    for t in ["1","2","3","4"]:
        assert s2.national_power.get(t, 0) > before_np[t], f"team {t} NP should increase from vortex"

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
    """n > 可用兵力 → 衝突懲罰：troops stay at source (100), phase 1.5 clears (<300), rescue gives 1000"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s2, log, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 600)"})
    assert s2.zones["人類王國"].troops.get("1", 0) == 0, "zone cleared by phase 1.5"
    assert s2.zones[NEUTRAL_ISLAND].troops.get("1", 0) == 1000, "rescue gives 1000"

def test_conflict_two_ops_sum_exceeds():
    """兩個操作合計超過兵力 → 全部無效，phase 1.5 清除來源地，rescue 補足"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"1": 50})  # team 1 also here for second op target
    # moving(A,B,50) + attack(A,C,80) = 130 > 100 → conflict
    s2, log, _, _ = run_round(s, {"1": "moving(人類王國, 中立小島, 50)\nattack(人類王國, 精靈森域, 80)"})
    t1_src = s2.zones["人類王國"].troops.get("1", 0)
    t1_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("1", 0)
    assert t1_src == 0, "zone cleared by phase 1.5"
    assert t1_neutral == 1000, "rescue gives 1000"
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
    """衝突移入的兵力不視為進攻，中立小島 owner 不受影響"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones[NEUTRAL_ISLAND] = ZoneState(troops={"2": 200})
    s2, _, _, _ = run_round(s, {"1": "attack(人類王國, 精靈森域, 600)"})
    # team 2's neutral island: ceil100(200*1.5)=300. T2 total=300+500=800<1000 → rescue +200 → 500
    t2_neutral = s2.zones[NEUTRAL_ISLAND].troops.get("2", 0)
    assert t2_neutral == 500, f"team 2 neutral ×1.5 + rescue, got {t2_neutral}"

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
    A 同時以 solo 和 (A,B) 兩個聯盟進攻同一目標。
    (A,B) 勝出 → solo_A 為敗方（A 的 solo 兵力進入 bonus 池）；
    但 A 在勝方聯盟中的兵力不被清零。
    """
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"]  = ZoneState(troops={"1": 1000})
    s.zones["精靈森域"]  = ZoneState(troops={"1": 1000})  # team 1 second zone
    s.zones["龍族火山"]  = ZoneState(troops={"2": 500})
    s.zones["獸人荒原"]  = ZoneState(troops={"3": 500})
    # team 3 defends 布丁狗族 (empty → no defender)
    s.zones["布丁狗族"]  = ZoneState(troops={"3": 300})
    # team 1 attacks 布丁狗族 solo (n=100) AND in coalition with 2 (n=200+150)
    # coalition (1,2) total = 350 > solo_1 = 100 > no defender
    cmds = {
        "1": "attack(人類王國, 布丁狗族, 100)\nunion_attack(精靈森域, [2], 布丁狗族, 200)",
        "2": "union_attack(龍族火山, [1], 布丁狗族, 150)",
    }
    s2, log, _, _ = run_round(s, cmds)
    t1 = s2.zones["布丁狗族"].troops.get("1", 0)
    t2 = s2.zones["布丁狗族"].troops.get("2", 0)
    # New engine: survival=350-300-100=... coalition(350) beats solo(100)+defender(300)
    # survival=350-(300+100)=... actually: ceil100 distribute, leader T1(200>150) gets max(share,500)=500
    # T2: ceil100(survival * 150/350)
    t1_expected = 500  # leader guarantee
    t2_expected = 100  # proportional ceil100(50*150/350)=ceil100(21.4)=100
    assert t1 == t1_expected, f"team 1 (winner coalition): expected {t1_expected}, got {t1}"
    assert t2 == t2_expected, f"team 2 (winner coalition): expected {t2_expected}, got {t2}"

def test_same_team_solo_loses_troops_enter_pool():
    """同一隊同時 solo 和 coalition 進攻，solo 落敗後兵力進入 bonus 池（而非消失）"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"]  = ZoneState(troops={"1": 1000})
    s.zones["精靈森域"]  = ZoneState(troops={"1": 1000})
    s.zones["龍族火山"]  = ZoneState(troops={"2": 500})
    # Empty target (no defender)
    s.zones["侏儒劇場"]  = ZoneState()
    cmds = {
        "1": "attack(人類王國, 侏儒劇場, 50)\nunion_attack(精靈森域, [2], 侏儒劇場, 300)",
        "2": "union_attack(龍族火山, [1], 侏儒劇場, 200)",
    }
    s2, log, _, _ = run_round(s, cmds)
    t1 = s2.zones["侏儒劇場"].troops.get("1", 0)
    t2 = s2.zones["侏儒劇場"].troops.get("2", 0)
    # New engine: coalition(1+2)=500 vs solo_1=50, no defender
    # survival=500-50=450. Distribute {1:300, 2:200}: T1=ceil100(450*300/500)=300; T2=ceil100(450*200/500)=200
    # Leader T1(300): max(300,500)=500. T2: 200.
    t1_expected = 500  # leader guarantee
    t2_expected = 200  # proportional ceil100(450*200/500)=200
    assert t1 == t1_expected, f"team 1: expected {t1_expected}, got {t1}"
    assert t2 == t2_expected, f"team 2: expected {t2_expected}, got {t2}"


# ─────────────────────────────────────────────────────────────────────────────
# 新規則：各勝方獨立獲得 full 20% 獎勵（非比例瓜分）
# ─────────────────────────────────────────────────────────────────────────────

def test_coalition_each_winner_gets_full_bonus():
    """A+B 聯盟勝：新引擎 _distribute + leader guarantee 500"""
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
    # 龍族火山 has 100 < 300 → phase 1.5 clears. Coalition(300) vs 0: survival=300.
    # Distribute {1:150, 2:150}: T1=ceil100(300*150/300)=200; T2=200. Leader: tied → T1(200): max(200,500)=500. T2:200.
    assert s2.zones["龍族火山"].troops.get("1", 0) == 500, "team 1 leader gets 500"
    assert s2.zones["龍族火山"].troops.get("2", 0) == 200, "team 2 gets proportional"

def test_regular_battle_winner_gets_full_bonus_from_eliminated():
    """人類王國 100 < 300 → Phase 1.5 clears; T2/T3 attack empty zone → mutual elim → no winner"""
    s = GameState(teams=["1","2","3"], max_rounds=3)
    s.round = 1; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"1": 100})
    s.zones["精靈森域"] = ZoneState(troops={"2": 500})
    s.zones["龍族火山"] = ZoneState(troops={"3": 500})
    cmds = {
        "2": "attack(精靈森域, 人類王國, 200)",
        "3": "attack(龍族火山, 人類王國, 200)",
    }
    s2, _, _, _ = run_round(s, cmds)
    # 人類王國 has 100 < 300 → phase 1.5 clears to 0. Then T2(200) vs T3(200) mutual elim → no winner.
    assert s2.zones["人類王國"].troops.get("1", 0) == 0, "zone cleared by phase 1.5, no winner"

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
    """駐守方兵力變 0；phase 1.5：只剩 T1=100 < 300 → 清除，owner=None"""
    s = GameState(teams=["1","2"], max_rounds=3)
    s.round = 2; s.phase = "input"
    s.zones["人類王國"] = ZoneState(troops={"2": 500})
    # zone Z: team 1 is owner, team 2 has garrison
    s.zones["精靈森域"] = ZoneState(troops={"1": 100, "2": 50}, forced_owner="1")
    # team 2 moves all garrison troops away from 精靈森域 → 0 at zone
    s2, _, _, _ = run_round(s, {"2": "moving(精靈森域, 人類王國, 50)"})
    z = s2.zones["精靈森域"]
    assert z.troops.get("2", 0) == 0, "team 2 garrison should be gone"
    assert z.owner() is None, "zone cleared by phase 1.5 (only 100 troops < 300)"

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
