"""
Game engine for 最終大戰 / COCONUT WARS (COW).

Responsibilities:
- Validate commands against current game state
- Compute attack coalition validity (clique algorithm)
- Match help/accept pairs
- Execute a round (parallel simulation)
- Settle: battles (Situation A/B/tie), coconuts, neutral island, resource points
"""
from __future__ import annotations
import copy
import math
from dataclasses import dataclass, field
from typing import Optional

from .state import (
    GameState, ZoneState,
    ISLANDS, NEUTRAL_ISLAND, RESOURCE_POINTS,
    TERRITORY_POWER, ALL_TEAMS,
)
from .parser import ParsedCommand, CommandResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ceil100(x) -> int:
    """Round up to nearest 100; minimum 0."""
    if x <= 0:
        return 0
    return int(math.ceil(x / 100)) * 100


# ── Validation result ────────────────────────────────────────────────────────

@dataclass
class ValidatedCmd:
    result: CommandResult
    team: str
    valid: bool = False
    reason: str = ""
    warning: str = ""
    # help/accept matching
    help_matched: bool = False   # help: found a matching accept
    help_partner: str = ""       # help/accept: the partner team
    # attack coalition (same as before)
    effective_allies: list = field(default_factory=list)


# ── Validator ────────────────────────────────────────────────────────────────

class RoundValidator:
    """
    Validates all commands submitted for the current round.
    Re-run after each new team submits to update coalition/help status.
    """

    def __init__(self, state: GameState):
        self.state = state

    def validate_all(
        self,
        cmds_by_team: dict[str, list[CommandResult]],
    ) -> dict[str, list[ValidatedCmd]]:
        """
        cmds_by_team: team → list[CommandResult] (already parsed)
        Returns: team → list[ValidatedCmd]
        """
        # Step 1: basic per-command validation
        vcmds: dict[str, list[ValidatedCmd]] = {}
        for team, results in cmds_by_team.items():
            vcmds[team] = [self._validate_one(team, r) for r in results]

        # Step 2: enforce 5-op limit (accept does NOT count)
        for team, vlist in vcmds.items():
            ok_count = 0
            for vc in vlist:
                if vc.valid and vc.result.command:
                    op = vc.result.command.op
                    if op not in ("set", "accept"):
                        ok_count += 1
                        if ok_count > 5:
                            vc.valid = False
                            vc.reason = "超過每回合 5 次操作上限（靜默忽略）"

        # Step 3: per-source conflict check (sum troops from same S)
        for team, vlist in vcmds.items():
            zone_demand: dict[str, int] = {}
            for vc in vlist:
                if not vc.valid:
                    continue
                cmd = vc.result.command
                if cmd.op in ("move", "help", "attack"):
                    zone_demand[cmd.source] = zone_demand.get(cmd.source, 0) + cmd.n
            for zone, demand in zone_demand.items():
                available = self.state.zones[zone].troops.get(team, 0)
                if demand > available:
                    for vc in vlist:
                        if not vc.valid:
                            continue
                        cmd = vc.result.command
                        if cmd and cmd.op in ("move", "help", "attack") \
                                and cmd.source == zone:
                            vc.valid = False
                            vc.reason = (
                                f"兵力衝突：{zone} 現有 {available}，"
                                f"所有操作合計需 {demand}，"
                                "涉及此出發區域的指令全部無效，兵力原地遣返"
                            )

        # Step 4: match help/accept pairs
        self._resolve_help_accept(vcmds)

        # Step 5: resolve attack coalitions
        self._resolve_attack_coalitions(vcmds)

        return vcmds

    def _validate_one(self, team: str, result: CommandResult) -> ValidatedCmd:
        vc = ValidatedCmd(result=result, team=team)
        if not result.ok:
            vc.valid = False
            vc.reason = result.error
            return vc

        cmd = result.command
        state = self.state

        if cmd.op == "set":
            if team != "ADMIN":
                vc.valid = False
                vc.reason = "set() 操作僅限管理員"
                return vc
            if cmd.nation not in ("\x00", "") and cmd.nation not in state.teams:
                vc.valid = False
                vc.reason = f"未知隊伍 {cmd.nation}（forced_owner 必須為有效隊伍）"
                return vc
            vc.valid = True
            return vc

        if cmd.op == "move":
            s_zone = state.zones.get(cmd.source)
            if s_zone is None:
                vc.valid = False
                vc.reason = f"未知區域 {cmd.source}"
                return vc
            if not self._team_controls_zone(team, cmd.source):
                vc.valid = False
                vc.reason = f"{cmd.source} 不在己方控制下（無法移動）"
                return vc
            if cmd.n <= 0:
                vc.valid = False
                vc.reason = "兵力數必須為正整數"
                return vc
            if cmd.target in RESOURCE_POINTS and state.round == 1:
                vc.valid = False
                vc.reason = f"第一回合不可移動至資源點 {cmd.target}"
                return vc
            # Can move to own/neutral/resource zones
            if cmd.target != NEUTRAL_ISLAND and cmd.target not in RESOURCE_POINTS:
                if not self._team_controls_zone(team, cmd.target):
                    vc.valid = False
                    vc.reason = f"move 不可移動至他國領地 {cmd.target}"
                    return vc
            vc.valid = True
            return vc

        if cmd.op == "help":
            if cmd.nation == team:
                vc.valid = False
                vc.reason = "help 不能與自己協防"
                return vc
            if cmd.nation not in state.teams:
                vc.valid = False
                vc.reason = f"未知隊伍 {cmd.nation}"
                return vc
            if not self._team_controls_zone(team, cmd.source):
                vc.valid = False
                vc.reason = f"{cmd.source} 不在己方控制下"
                return vc
            if cmd.n <= 0:
                vc.valid = False
                vc.reason = "兵力數必須為正整數"
                return vc
            if cmd.target in RESOURCE_POINTS and state.round == 1:
                vc.valid = False
                vc.reason = f"第一回合不可移動至資源點 {cmd.target}"
                return vc
            if not self._team_owns_territory(cmd.nation, cmd.target):
                vc.valid = False
                vc.reason = f"{cmd.target} 不是 {cmd.nation} 的領地（help 目標必須是盟友領地）"
                return vc
            vc.valid = True
            return vc

        if cmd.op == "accept":
            if cmd.nation == team:
                vc.valid = False
                vc.reason = "accept 不能接受自己的協防"
                return vc
            if cmd.nation not in state.teams:
                vc.valid = False
                vc.reason = f"未知隊伍 {cmd.nation}"
                return vc
            if not self._team_owns_territory(team, cmd.target):
                vc.valid = False
                vc.reason = f"{cmd.target} 不是己方領地（accept 目標必須是己方領地）"
                return vc
            vc.valid = True
            return vc

        if cmd.op == "attack":
            if not self._team_controls_zone(team, cmd.source):
                vc.valid = False
                vc.reason = f"{cmd.source} 不在己方控制下"
                return vc
            if cmd.n <= 0:
                vc.valid = False
                vc.reason = "兵力數必須為正整數"
                return vc
            if cmd.target in RESOURCE_POINTS and state.round == 1:
                vc.valid = False
                vc.reason = f"第一回合不可進攻資源點 {cmd.target}"
                return vc
            if state.zones[cmd.target].troops.get(team, 0) > 0:
                vc.valid = False
                vc.reason = f"不可進攻自己有駐兵的領地 {cmd.target}（駐守叛變已廢除）"
                return vc
            # Penalized but valid: only targeting neutral island is a world law violation
            if cmd.target == NEUTRAL_ISLAND:
                vc.warning = f"進攻中立小島違反世界法：{cmd.n} 兵力損失"
            # Check allies list: can't include self
            if team in (cmd.allies or []):
                vc.valid = False
                vc.reason = "attack 的盟友列表不能包含自己"
                return vc
            vc.valid = True
            return vc

        vc.valid = False
        vc.reason = f"未知操作 {cmd.op}"
        return vc

    def _team_controls_zone(self, team: str, zone: str) -> bool:
        return self.state.zones[zone].troops.get(team, 0) > 0

    def _team_owns_territory(self, team: str, zone: str) -> bool:
        return self.state.zones[zone].owner() == team

    def _resolve_help_accept(self, vcmds: dict[str, list[ValidatedCmd]]):
        """Match help/accept pairs and mark matched help commands."""
        # Collect valid help commands: (team, cmd, vc)
        helps = [
            (team, vc.result.command, vc)
            for team, vlist in vcmds.items()
            for vc in vlist
            if vc.valid and vc.result.command and vc.result.command.op == "help"
        ]
        # Collect valid accept commands: (team, cmd, vc)
        accepts = [
            (team, vc.result.command, vc)
            for team, vlist in vcmds.items()
            for vc in vlist
            if vc.valid and vc.result.command and vc.result.command.op == "accept"
        ]

        matched_accepts = set()
        matched_helps = set()

        for hi, (ht, hc, hvc) in enumerate(helps):
            if hi in matched_helps:
                continue
            for ai, (at, ac, avc) in enumerate(accepts):
                if ai in matched_accepts:
                    continue
                # Match: help's target == accept's target
                #        help's nation == accept team (who is accepting)
                #        accept's nation == help team (who is helping)
                if (hc.target == ac.target
                        and hc.nation == at
                        and ac.nation == ht):
                    hvc.help_matched = True
                    hvc.help_partner = at
                    matched_helps.add(hi)
                    matched_accepts.add(ai)
                    break

    def _resolve_attack_coalitions(self, vcmds: dict[str, list[ValidatedCmd]]):
        """
        Resolve attack coalitions with overlap-resolution.

        Step 1: find all valid cliques (every member mutually declares all others).
        Step 2: if two valid cliques overlap (share ≥1 team), they conflict.
                Resolve by priority (descending):
                  a) number of teams in the clique
                  b) total attack troops of the clique
                  c) total game-state troops of all teams in the clique
                  d) deterministic tie-break (min team id wins)
                Winner proceeds; loser's exclusive members are invalidated (return).
        Step 3: repeat until no overlapping cliques remain.
        Solo attackers (empty allies list) always proceed unchanged.
        """
        atk_by_target: dict[str, list[tuple[str, ParsedCommand, ValidatedCmd]]] = {}
        for team, vlist in vcmds.items():
            for vc in vlist:
                if not vc.valid or not vc.result.command:
                    continue
                cmd = vc.result.command
                if cmd.op != "attack":
                    continue
                if cmd.target == NEUTRAL_ISLAND:
                    continue
                atk_by_target.setdefault(cmd.target, []).append((team, cmd, vc))

        for target, group in atk_by_target.items():
            team_allies: dict[str, set[str]] = {}
            troops_map: dict[str, int] = {}
            vcs_per_team: dict[str, list[ValidatedCmd]] = {}
            all_attacking = {t for t, _, _ in group}

            for t, cmd, vc in group:
                valid_allies = set(cmd.allies or []) & all_attacking
                team_allies.setdefault(t, set()).update(valid_allies)
                troops_map[t] = troops_map.get(t, 0) + cmd.n
                vcs_per_team.setdefault(t, []).append(vc)

            solo_teams = {t for t in all_attacking if not team_allies.get(t)}
            coalition_teams = all_attacking - solo_teams

            assignment: dict[str, str] = {}
            remaining = set(coalition_teams)
            cid_counter = 0

            while remaining:
                curr_allies = {t: team_allies[t] & remaining for t in remaining}
                cliques = _find_all_cliques(remaining, curr_allies)

                if not cliques:
                    # No mutual coalition possible — all remaining attack solo
                    for t in remaining:
                        assignment[t] = f"solo_{t}"
                    remaining.clear()
                    break

                def _clique_key(c: frozenset) -> tuple:
                    cnt   = len(c)                     # ① more teams wins
                    atk   = sum(troops_map.get(t, 0) for t in c)  # ② more attack troops
                    game  = sum(self.state.total_troops(t) for t in c)  # ③ total game troops
                    det   = -min(int(t) for t in c)   # ④ deterministic tie-break
                    return (cnt, atk, game, det)

                cliques_sorted = sorted(cliques, key=_clique_key, reverse=True)

                # Find first pair of overlapping cliques (highest-priority first)
                overlap_pair: Optional[tuple[frozenset, frozenset]] = None
                for i in range(len(cliques_sorted)):
                    for j in range(i + 1, len(cliques_sorted)):
                        if cliques_sorted[i] & cliques_sorted[j]:
                            overlap_pair = (cliques_sorted[i], cliques_sorted[j])
                            break
                    if overlap_pair:
                        break

                if overlap_pair is None:
                    # No overlaps: take the highest-priority clique
                    winner = cliques_sorted[0]
                    cid = f"C{cid_counter}"
                    cid_counter += 1
                    for t in winner:
                        assignment[t] = cid
                        remaining.discard(t)
                    continue

                winner_c, loser_c = overlap_pair
                cid = f"C{cid_counter}"
                cid_counter += 1
                for t in winner_c:
                    assignment[t] = cid
                    remaining.discard(t)
                for t in loser_c - winner_c:
                    assignment[t] = f"return_{t}"
                    remaining.discard(t)

            coalition_members: dict[str, list[str]] = {}
            for t, cid in assignment.items():
                coalition_members.setdefault(cid, []).append(t)

            for t, vcs in vcs_per_team.items():
                cid = assignment.get(t, f"solo_{t}")
                if cid.startswith("return_"):
                    for vc in vcs:
                        vc.valid = False
                        vc.reason = "聯盟衝突：被較強聯盟擊敗，兵力原地遣返"
                else:
                    allies = [m for m in coalition_members.get(cid, []) if m != t]
                    for vc in vcs:
                        vc.effective_allies = allies

            for t in solo_teams:
                for vc in vcs_per_team[t]:
                    vc.effective_allies = []


# ── Coalition helpers ─────────────────────────────────────────────────────────

def _find_all_cliques(
    teams: set[str],
    named: dict[str, set[str]],
) -> list[frozenset[str]]:
    """
    Return all valid coalitions of size >= 2.
    A coalition C is valid iff every member lists all other members.
    """
    from itertools import combinations
    team_list = sorted(teams)
    cliques = []
    for size in range(2, len(team_list) + 1):
        for combo in combinations(team_list, size):
            combo_set = frozenset(combo)
            if all(combo_set - {t} <= named.get(t, set()) for t in combo):
                cliques.append(combo_set)
    return cliques


# ── Battle resolution helpers ─────────────────────────────────────────────────

def _battle_find_winner(
    groups: dict[str, dict[str, int]],
) -> tuple[Optional[str], list[list[str]]]:
    """
    Find the battle winner by iteratively eliminating tied groups.
    Returns (winner_cid, list_of_eliminated_rounds).
    Each eliminated_round is a list of coalition ids that tied and died.
    If all groups are eliminated, winner_cid is None.
    """
    active = {cid: tm for cid, tm in groups.items() if sum(tm.values()) > 0}
    eliminated_rounds: list[list[str]] = []

    while active:
        totals = {cid: sum(tm.values()) for cid, tm in active.items()}
        max_total = max(totals.values())
        tied = [cid for cid, v in totals.items() if v == max_total]

        if len(tied) == 1:
            return tied[0], eliminated_rounds

        # Tie-break: smallest coalition wins (solo beats equal-force coalition)
        min_size = min(len(active[c]) for c in tied)
        smallest = [c for c in tied if len(active[c]) == min_size]

        if len(smallest) == 1:
            return smallest[0], eliminated_rounds

        # All tied with same size → mutual elimination
        eliminated_rounds.append(smallest)
        for cid in smallest:
            del active[cid]

    return None, eliminated_rounds


def _distribute_situation_a(
    winner_troops: dict[str, int],
    survival: int,
) -> dict[str, int]:
    """
    Situation A: distribute survival among winning coalition.
    Proportional to sent troops, ceil to 100, leader guaranteed ≥ 500.
    """
    winner_total = sum(winner_troops.values())
    if winner_total == 0:
        return {}
    result: dict[str, int] = {}
    for team, n in winner_troops.items():
        share = survival * n / winner_total
        result[team] = _ceil100(share)
    # Leader guarantee ≥ 500
    leader = max(winner_troops, key=winner_troops.get)
    if result.get(leader, 0) < 500:
        result[leader] = 500
    return result


def _distribute_situation_b(
    defender_troops: dict[str, int],
    original_defender_total: int,
    all_attacker_total: int,
    strongest_attacker_total: int,
) -> dict[str, int]:
    """
    Situation B: distribute to winning defenders.
    survival_base = max(original - strongest_attacker, original // 2)
    prisoner_bonus = 20% of all_attacker_total (raw, rounded at distribution)
    Total split proportionally, ceil to 100.
    """
    raw_survival = original_defender_total - strongest_attacker_total
    survival_base = max(raw_survival, original_defender_total // 2)
    prisoner_bonus_raw = int(all_attacker_total * 0.20)
    total_outcome = survival_base + prisoner_bonus_raw

    if original_defender_total == 0:
        return {}

    result: dict[str, int] = {}
    for team, n in defender_troops.items():
        share = total_outcome * n / original_defender_total
        result[team] = _ceil100(share)
    return result


# ── Round executor ────────────────────────────────────────────────────────────

def execute_round(
    state: GameState,
    vcmds: dict[str, list[ValidatedCmd]],
) -> tuple[GameState, list[str], list[dict]]:
    """
    Execute all valid commands for a round.
    Returns (new_state, log_lines, animation_events).

    Execution order:
    1. Simultaneous moves (move / matched help+accept / attack departures)
    1.5. 300-min defense check: islands with < 300 total troops become empty
    2. Settle battles (garrison betrayal, Situation A/B/tie)
    3. Coconuts from territories (1000 per island, proportional)
    4. Neutral island × 1.5 (ceil to 100)
    4.5. Low-troop rescue: total < 1000 → top up to 1000
    5. Resource points (from round 2)
    0. Admin set() (deferred — runs last so team commands read clean state)
    """
    log: list[str] = []
    anim: list[dict] = []
    new_state = state.copy()

    _has_admin_cmds = any(vc.valid for vc in vcmds.get("ADMIN", []))
    _has_non_admin_input = any(
        len(vlist) > 0 for team, vlist in vcmds.items() if team != "ADMIN"
    )
    _admin_only = _has_admin_cmds and not _has_non_admin_input

    # ── Phase 1: Simultaneous moves ───────────────────────────────────────
    delta_out: dict[str, dict[str, int]] = {}
    delta_in: dict[str, dict[str, int]] = {}
    attacks: dict[str, list[dict]] = {}  # target → [{team, n, coalition}]

    def add_out(zone, team, n):
        delta_out.setdefault(zone, {}).setdefault(team, 0)
        delta_out[zone][team] += n

    def add_in(zone, team, n):
        delta_in.setdefault(zone, {}).setdefault(team, 0)
        delta_in[zone][team] += n

    for team, vlist in vcmds.items():
        for vc in vlist:
            if not vc.valid:
                continue
            cmd = vc.result.command
            if cmd.op == "set":
                continue

            if cmd.op == "move":
                add_out(cmd.source, team, cmd.n)
                add_in(cmd.target, team, cmd.n)
                log.append(f"{team}: move({cmd.source} → {cmd.target}, {cmd.n})")
                anim.append({"type": "move", "team": team, "from": cmd.source,
                              "to": cmd.target, "n": cmd.n, "kind": "move"})

            elif cmd.op == "help":
                if vc.help_matched:
                    add_out(cmd.source, team, cmd.n)
                    add_in(cmd.target, team, cmd.n)
                    log.append(f"{team}: help 成功（{vc.help_partner} 同意），"
                               f"{cmd.n} 兵從 {cmd.source} → {cmd.target}")
                    anim.append({"type": "move", "team": team, "from": cmd.source,
                                  "to": cmd.target, "n": cmd.n, "kind": "help"})
                else:
                    log.append(f"{team}: help({cmd.target}) 未配對，兵力原地遣返")

            elif cmd.op == "accept":
                log.append(f"{team}: accept({cmd.target}, {cmd.nation}) 發出")

            elif cmd.op == "attack":
                add_out(cmd.source, team, cmd.n)
                if cmd.target == NEUTRAL_ISLAND:
                    # Penalty: troops lost immediately
                    log.append(f"[懲罰] {team}: attack→{cmd.target} 違反世界法，損失 {cmd.n}")
                    anim.append({"type": "move", "team": team, "from": cmd.source,
                                  "to": cmd.target, "n": cmd.n, "kind": "penalty"})
                else:
                    all_in_coalition = sorted([team] + vc.effective_allies)
                    cid = "coa_" + "_".join(all_in_coalition) + "_at_" + cmd.target
                    attacks.setdefault(cmd.target, []).append({
                        "team": team,
                        "n": cmd.n,
                        "coalition": cid,
                    })
                    allies_str = "+".join(vc.effective_allies) if vc.effective_allies else "solo"
                    log.append(f"{team}: attack → {cmd.target}, 聯盟:{allies_str}, 出兵:{cmd.n}")
                    anim.append({"type": "move", "team": team, "from": cmd.source,
                                  "to": cmd.target, "n": cmd.n, "kind": "attack",
                                  "allies": vc.effective_allies})

    # Apply delta_out
    for zone, team_amounts in delta_out.items():
        for team, amount in team_amounts.items():
            new_state.zones[zone].troops[team] = max(
                0, new_state.zones[zone].troops.get(team, 0) - amount
            )

    # Apply delta_in for non-attack moves
    for zone, team_amounts in delta_in.items():
        for team, amount in team_amounts.items():
            new_state.zones[zone].troops[team] = \
                new_state.zones[zone].troops.get(team, 0) + amount

    # ── Phase 1.5: 300-min defense check ──────────────────────────────────
    if not _admin_only:
        for zone in ISLANDS:
            zs = new_state.zones[zone]
            total = zs.total()
            if 0 < total < 300:
                log.append(f"[防守不足] {zone}: 留守兵力 {total} < 300，空島化（兵力解散）")
                new_state.zones[zone] = ZoneState(troops={}, forced_owner=None)

    # ── Phase 2: Resolve battles ──────────────────────────────────────────
    if not _admin_only:
        for target, attacker_list in attacks.items():
            # Build coalition_troops (summing multi-source attacks per coalition)
            coalition_troops: dict[str, dict[str, int]] = {}
            for a in attacker_list:
                ct = coalition_troops.setdefault(a["coalition"], {})
                ct[a["team"]] = ct.get(a["team"], 0) + a["n"]

            if not coalition_troops:
                continue

            # Defender = post-Phase1 troops at target
            defender_troops = dict(new_state.zones[target].troops)
            original_defender_total = sum(defender_troops.values())
            total_attacker = sum(sum(tm.values()) for tm in coalition_troops.values())

            # ── Step 1: Situation A/B determination ───────────────────────
            # Situation B (defender wins): defender_total >= total_attacker (tie → defender wins)
            if original_defender_total >= total_attacker:
                strongest_attacker = max(
                    (sum(tm.values()) for tm in coalition_troops.values()), default=0
                )
                new_troops = _distribute_situation_b(
                    defender_troops, original_defender_total,
                    total_attacker, strongest_attacker
                )
                new_forced_owner = state.zones[target].forced_owner
                loser_teams = [t for tm in coalition_troops.values() for t in tm]
                log.append(
                    f"[戰鬥-B] {target}：守方勝（{original_defender_total}兵），"
                    f"攻方共={total_attacker}；"
                    f"守方後：{', '.join(f'{t}:{n}' for t,n in new_troops.items())}"
                )
                anim.append({"type": "battle", "zone": target,
                              "winner_teams": list(defender_troops.keys()),
                              "loser_teams": loser_teams,
                              "winner_total": original_defender_total, "bonus": 0})

            else:
                # Situation A (attacker side wins): total_attacker > defender_total
                # Find winning coalition among attackers (tie-break: smallest coalition)
                winner_cid, eliminated_rounds = _battle_find_winner(coalition_troops)

                # Log attacker-vs-attacker tie eliminations
                for round_elim in eliminated_rounds:
                    elim_str = " vs ".join(
                        "+".join(sorted(coalition_troops[c].keys())) for c in round_elim
                    )
                    log.append(f"[戰鬥] {target}：同歸於盡（{elim_str}）")

                if winner_cid is None:
                    # All attacker coalitions eliminated each other → defender retains
                    orig_fo = new_state.zones[target].forced_owner
                    new_state.zones[target] = ZoneState(
                        troops=defender_troops, forced_owner=orig_fo
                    )
                    if orig_fo or defender_troops:
                        log.append(f"[戰鬥] {target}：攻方全滅，守方保留")
                    else:
                        log.append(f"[戰鬥] {target}：全部同歸於盡，空島")
                    anim.append({"type": "battle", "zone": target,
                                  "winner_teams": [], "loser_teams": [],
                                  "winner_total": 0, "bonus": 0})
                    continue

                # Winner coalition vs defender → apply Situation A
                winner_total = sum(coalition_troops[winner_cid].values())
                # Strongest loser = max(defender, other losing attacker coalitions)
                other_totals = [
                    sum(tm.values())
                    for cid, tm in coalition_troops.items()
                    if cid != winner_cid
                ]
                strongest_loser_total = max([original_defender_total] + other_totals)
                survival = max(0, winner_total - strongest_loser_total)

                new_troops = _distribute_situation_a(
                    coalition_troops[winner_cid], survival
                )

                # New owner: team with most attack troops in winning coalition
                win_atk_troops = coalition_troops[winner_cid]
                new_forced_owner = max(win_atk_troops, key=win_atk_troops.get) if win_atk_troops else None

                all_groups_for_log: dict[str, dict[str, int]] = dict(coalition_troops)
                if defender_troops:
                    all_groups_for_log["defender"] = defender_troops
                loser_teams = [
                    t for cid, tm in all_groups_for_log.items() if cid != winner_cid
                    for t in tm
                ]
                log.append(
                    f"[戰鬥-A] {target}：進攻方 {'+'.join(coalition_troops[winner_cid].keys())} 勝"
                    f"（{winner_total}兵），存活={survival}；"
                    f"後：{', '.join(f'{t}:{n}' for t,n in new_troops.items())}"
                )
                anim.append({"type": "battle", "zone": target,
                              "winner_teams": list(coalition_troops[winner_cid].keys()),
                              "loser_teams": loser_teams,
                              "winner_total": winner_total, "bonus": survival})

            # Finalize zone state
            new_troops = {t: n for t, n in new_troops.items() if n > 0}
            new_zone = ZoneState(troops=new_troops, forced_owner=new_forced_owner)
            new_state.zones[target] = new_zone

    if not _admin_only:
        # ── Phase 3: Coconuts from territories ────────────────────────────
        for zone in ISLANDS:
            x = TERRITORY_POWER.get(zone, 1000)
            z_state = new_state.zones[zone]
            total_t = z_state.total()
            owner = z_state.owner()

            if total_t == 0:
                # 0 troops but forced_owner → still earns full coconuts
                if owner:
                    new_state.national_power[owner] = \
                        new_state.national_power.get(owner, 0) + x
                    log.append(f"[椰子] {zone}({x})：{owner} +{x}（0兵力領主）")
                continue

            if total_t > 0 and len(z_state.troops) == 1:
                # Sole occupant
                team = next(iter(z_state.troops))
                new_state.national_power[team] = \
                    new_state.national_power.get(team, 0) + x
                log.append(f"[椰子] {zone}({x})：{team} +{x}")
            else:
                # Co-occupied: proportional, ceil to 100
                gained = {}
                for team, troops in z_state.troops.items():
                    if troops > 0:
                        share = _ceil100(x * troops / total_t)
                        if share > 0:
                            gained[team] = share
                for team, share in gained.items():
                    new_state.national_power[team] = \
                        new_state.national_power.get(team, 0) + share
                log.append(
                    f"[椰子] {zone}({x})：" +
                    ", ".join(f"{t}+{s}" for t, s in gained.items())
                )

        # ── Phase 4: Neutral island × 1.5 (ceil to 100) ───────────────────
        neutral = new_state.zones[NEUTRAL_ISLAND]
        for team in list(neutral.troops.keys()):
            n = neutral.troops.get(team, 0)
            if n > 0:
                new_n = _ceil100(n * 1.5)
                neutral.troops[team] = new_n
                log.append(f"[中立] {team} 兵力 {n} × 1.5 → {new_n}")

        # ── Phase 4.5: Low-troop rescue (total < 1000 → top up to 1000) ───
        for team in new_state.teams:
            total = new_state.total_troops(team)
            if total < 1000:
                top_up = 1000 - total
                new_state.zones[NEUTRAL_ISLAND].troops[team] = \
                    new_state.zones[NEUTRAL_ISLAND].troops.get(team, 0) + top_up
                log.append(
                    f"[救濟] {team} 全場兵力 {total} < 1000，"
                    f"補充 {top_up} 至中立小島（共達 1000）"
                )

        # ── Phase 5: Resource points (from round 2) ────────────────────────
        if new_state.round >= 2:
            _settle_resource_points(new_state, log)

    # Advance round
    if not _admin_only:
        new_state.sub_round = 0
        new_state.round += 1
        if new_state.round > new_state.max_rounds:
            new_state.phase = "done"
        else:
            new_state.phase = "input"
    else:
        new_state.sub_round = state.sub_round + 1
        new_state.phase = state.phase

    new_state.round_commands = {t: [] for t in new_state.teams}
    new_state.round_commands["ADMIN"] = []

    # Persist ownership for zones not yet tracked
    for zone, zs in new_state.zones.items():
        if zs.forced_owner is None and zs.troops:
            by_t = sorted(zs.troops.items(), key=lambda kv: kv[1], reverse=True)
            if len(by_t) == 1 or by_t[0][1] > by_t[1][1]:
                new_state.zones[zone].forced_owner = by_t[0][0]

    # ── Phase 0: Admin set() (deferred) ───────────────────────────────────
    for team, vlist in vcmds.items():
        for vc in vlist:
            if not vc.valid:
                continue
            cmd = vc.result.command
            if cmd.op == "set":
                zone = cmd.source
                new_troops: dict[str, int] = {}
                for t, n in cmd.allies:
                    if n > 0:
                        new_troops[t] = n
                existing_fo = new_state.zones[zone].forced_owner
                if cmd.nation == "\x00":
                    fo = existing_fo
                elif cmd.nation == "":
                    fo = None
                else:
                    fo = cmd.nation

                new_state.zones[zone] = ZoneState(troops=new_troops, forced_owner=fo)
                parts = []
                if new_troops:
                    parts.append(", ".join(f"{t}:{n}" for t, n in new_troops.items()))
                else:
                    parts.append("（清空）")
                if fo:
                    parts.append(f"佔領國={fo}")
                elif cmd.nation == "":
                    parts.append("佔領國已清除")
                log.append(f"[管理員] 設定 {zone}：{'  '.join(parts)}")

    # Remove all 0-troop entries
    for zs in new_state.zones.values():
        for team in [t for t, n in zs.troops.items() if n == 0]:
            del zs.troops[team]

    return new_state, log, anim


def _settle_resource_points(state: GameState, log: list[str]):
    """Settle 迷霧島, 金錢島 resource points (round 2+)."""

    # 迷霧島: ≤4 teams → each gets +2000 troops, +1000 coconuts; >4 teams → nothing
    r1 = state.zones.get("迷霧島")
    if r1:
        teams_present = [t for t, n in r1.troops.items() if n > 0]
        n_teams = len(teams_present)
        if n_teams == 0:
            pass  # empty, no action
        elif n_teams <= 4:
            for team in teams_present:
                state.zones["迷霧島"].troops[team] = r1.troops[team] + 2000
                state.national_power[team] = state.national_power.get(team, 0) + 1000
                log.append(f"[迷霧島] {team} +2000 兵力, +1000 椰子（{n_teams} 隊）")
        else:
            log.append(f"[迷霧島] {n_teams} 隊超過 4 隊上限，無產出")

    # 金錢島: all teams present split 3000 coconuts equally (ceil to 100)
    r2 = state.zones.get("金錢島")
    if r2:
        teams_present = [t for t, n in r2.troops.items() if n > 0]
        n_teams = len(teams_present)
        if n_teams > 0:
            share = _ceil100(3000 / n_teams)
            for team in teams_present:
                state.national_power[team] = state.national_power.get(team, 0) + share
                log.append(f"[金錢島] {team} +{share} 椰子（3000 ÷ {n_teams}，取百位）")
