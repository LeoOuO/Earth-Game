"""
Game engine for 最終大戰 (WWW).

Responsibilities:
- Validate commands against current game state
- Compute union / union_attack coalition validity
- Execute a round (parallel simulation)
- Settle: battles, national power, neutral island, resource points
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


# ── Validation result ────────────────────────────────────────────────────────

@dataclass
class ValidatedCmd:
    result: CommandResult   # original parse result
    team: str
    valid: bool = False
    reason: str = ""
    warning: str = ""  # non-fatal warning (valid but penalized)
    # Union-specific
    union_status: str = ""    # "" | "pending" | "confirmed"
    union_partner: str = ""   # partner team letter for union
    union_role: str = ""      # "requesting" | "accepting"
    # union_attack-specific
    effective_allies: list = field(default_factory=list)  # resolved coalition members


# ── Validator ────────────────────────────────────────────────────────────────

class RoundValidator:
    """
    Validates all commands submitted so far for the current round.
    Re-run after each new team submits to update union/union_attack status.
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
        # ── Step 1: basic per-command validation ──────────────────────────
        vcmds: dict[str, list[ValidatedCmd]] = {}
        for team, results in cmds_by_team.items():
            vcmds[team] = [self._validate_one(team, r) for r in results]

        # ── Step 2: enforce 5-op limit per team ──────────────────────────
        # Only valid commands count; truly-invalid commands (無效操作) do not consume slots.
        for team, vlist in vcmds.items():
            ok_count = 0
            for vc in vlist:
                if vc.valid and vc.result.command and vc.result.command.op != "set":
                    ok_count += 1
                    if ok_count > 5:
                        vc.valid = False
                        vc.reason = "超過每回合 5 次操作上限（靜默忽略）"

        # ── Step 3: per-territory conflict check ─────────────────────────
        # Sum troops required from each source zone per team
        for team, vlist in vcmds.items():
            zone_demand: dict[str, int] = {}
            for vc in vlist:
                if not vc.valid:
                    continue
                cmd = vc.result.command
                # Accepting unions cost no troops for this team
                if cmd.op == "union" and vc.union_role == "accepting":
                    continue
                if cmd.op in ("moving", "attack", "union", "union_attack"):
                    zone_demand[cmd.source] = zone_demand.get(cmd.source, 0) + cmd.n
            # Check each zone
            for zone, demand in zone_demand.items():
                available = self.state.zones[zone].troops.get(team, 0)
                if demand > available:
                    # Invalidate all ops from this zone for this team
                    for vc in vlist:
                        if not vc.valid:
                            continue
                        cmd = vc.result.command
                        if cmd and cmd.op in ("moving","attack","union","union_attack") \
                                and cmd.source == zone:
                            vc.valid = False
                            vc.reason = (
                                f"兵力衝突：{zone} 現有 {available}，"
                                f"所有操作合計需 {demand}，"
                                "涉及此出發區域的操作全部無效，兵力移入中立區域"
                            )

        # ── Step 4: union status ──────────────────────────────────────────
        self._resolve_unions(vcmds)

        # ── Step 5: union_attack coalition ───────────────────────────────
        self._resolve_union_attacks(vcmds)

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

        # Check source belongs to team (or is neutral/resource for moving)
        s_zone = state.zones.get(cmd.source)
        if s_zone is None:
            vc.valid = False
            vc.reason = f"未知區域 {cmd.source}"
            return vc

        team_troops = s_zone.troops.get(team, 0)

        if cmd.op == "moving":
            # Source must be own or neutral island or resource point
            if not self._team_controls_zone(team, cmd.source):
                vc.valid = False
                vc.reason = f"{cmd.source} 不在己方控制下（無法移動）"
                return vc
            if cmd.n <= 0:
                vc.valid = False
                vc.reason = "兵力數必須為正整數（1以上）"
                return vc
            # Round-1 resource point restriction
            if cmd.target in RESOURCE_POINTS and state.round == 1:
                vc.valid = False
                vc.reason = f"第一回合不可移動至資源點 {cmd.target}"
                return vc
            if cmd.target == NEUTRAL_ISLAND or cmd.target in RESOURCE_POINTS:
                pass  # always movable (if not round-1 locked)
            elif not self._team_controls_zone(team, cmd.target):
                vc.valid = False
                vc.reason = f"moving 不可移動至他國領地 {cmd.target}"
                return vc
            # n > team_troops is caught by the conflict check (Step 3); triggers penalty

        elif cmd.op == "attack":
            if not self._team_controls_zone(team, cmd.source):
                vc.valid = False
                vc.reason = f"{cmd.source} 不在己方控制下"
                return vc
            if cmd.n <= 0:
                vc.valid = False
                vc.reason = "兵力數必須為正整數（1以上）"
                return vc
            # Round-1 resource point restriction (invalid, not penalized)
            if cmd.target in RESOURCE_POINTS and state.round == 1:
                vc.valid = False
                vc.reason = f"第一回合不可進攻資源點 {cmd.target}"
                return vc
            if self._team_owns_territory(team, cmd.target):
                vc.valid = False
                vc.reason = f"不可進攻己方領地 {cmd.target}"
                return vc
            # n > team_troops is caught by the conflict check (Step 3); triggers penalty
            # Valid but penalized: neutral island or resource point target
            if cmd.target == NEUTRAL_ISLAND:
                vc.warning = f"進攻中立小島違反世界法：{cmd.n} 兵力損失（自殺）"
            elif cmd.target in RESOURCE_POINTS:
                vc.warning = f"進攻資源點違反世界法：{cmd.n} 兵力損失（自殺）"

        elif cmd.op == "union":
            if cmd.nation == team:
                vc.valid = False
                vc.reason = "union 不能與自己結盟"
                return vc
            if cmd.nation not in state.teams:
                vc.valid = False
                vc.reason = f"未知隊伍 {cmd.nation}"
                return vc
            e_zone = state.zones.get(cmd.target)
            if e_zone is None:
                vc.valid = False
                vc.reason = f"未知區域 {cmd.target}"
                return vc
            is_p_territory = self._team_owns_territory(cmd.nation, cmd.target)
            is_our_territory = self._team_owns_territory(team, cmd.target)
            if is_our_territory:
                if cmd.n <= 0:
                    vc.valid = False
                    vc.reason = "兵力數必須為正整數（1以上）"
                    return vc
                # Accepting mode: we are agreeing to host P's troops. No troop cost.
                vc.union_role = "accepting"
            elif is_p_territory:
                # Requesting mode: we move n troops from S to E (P's territory).
                vc.union_role = "requesting"
                if not self._team_controls_zone(team, cmd.source):
                    vc.valid = False
                    vc.reason = f"{cmd.source} 不在己方控制下（無法移動）"
                    return vc
                if cmd.n <= 0:
                    vc.valid = False
                    vc.reason = "兵力數必須為正整數（1以上）"
                    return vc
                # n > team_troops caught by conflict check (Step 3)
            else:
                vc.valid = False
                vc.reason = (
                    f"union 目標 {cmd.target} 既非 {cmd.nation} 的領地，"
                    "也非己方領地"
                )
                return vc

        elif cmd.op == "union_attack":
            if not self._team_controls_zone(team, cmd.source):
                vc.valid = False
                vc.reason = f"{cmd.source} 不在己方控制下"
                return vc
            if team in cmd.allies:
                vc.valid = False
                vc.reason = "union_attack 的盟友列表不能包含自己"
                return vc
            if cmd.n <= 0:
                vc.valid = False
                vc.reason = "兵力數必須為正整數（1以上）"
                return vc
            # Round-1 resource point restriction (invalid)
            if cmd.target in RESOURCE_POINTS and state.round == 1:
                vc.valid = False
                vc.reason = f"第一回合不可進攻資源點 {cmd.target}"
                return vc
            if self._team_owns_territory(team, cmd.target):
                vc.valid = False
                vc.reason = f"不可進攻己方領地 {cmd.target}"
                return vc
            # E cannot be any ally's territory (駐守 OK, 領主 NG — §3.4)
            for ally in cmd.allies:
                if self._team_owns_territory(ally, cmd.target):
                    vc.valid = False
                    vc.reason = (
                        f"union_attack 目標 {cmd.target} 為盟友 {ally} 的領地，"
                        "不可聯合進攻盟友領地（若盟友只是駐守則允許）"
                    )
                    return vc
            # n > team_troops caught by conflict check (Step 3)
            # Valid but penalized: neutral island or resource point target
            if cmd.target == NEUTRAL_ISLAND:
                vc.warning = f"聯合進攻中立小島違反世界法：{cmd.n} 兵力損失（自殺）"
            elif cmd.target in RESOURCE_POINTS:
                vc.warning = f"聯合進攻資源點違反世界法：{cmd.n} 兵力損失（自殺）"

        vc.valid = True
        return vc

    def _team_controls_zone(self, team: str, zone: str) -> bool:
        """Team has any troops in this zone."""
        return self.state.zones[zone].troops.get(team, 0) > 0

    def _team_owns_territory(self, team: str, zone: str) -> bool:
        """Team is the majority (owner) of this zone."""
        return self.state.zones[zone].owner() == team

    def _resolve_unions(self, vcmds: dict[str, list[ValidatedCmd]]):
        """Match union pairs and update statuses."""
        # Collect valid union commands: (team, cmd, vc)
        union_list = [
            (team, vc.result.command, vc)
            for team, vlist in vcmds.items()
            for vc in vlist
            if vc.valid and vc.result.command and vc.result.command.op == "union"
        ]

        # A valid union pair: (A, B) where
        #   A submits union(S, E, B, n) and B submits union(S, E, A, n)
        #   (same S, same E, same n, P cross-matches teams)
        matched = set()  # indices into union_list
        for i, (t1, c1, vc1) in enumerate(union_list):
            if i in matched:
                continue
            for j, (t2, c2, vc2) in enumerate(union_list):
                if j <= i or j in matched:
                    continue
                # Match: same S, same E, same n; P values cross-match teams
                if (c1.nation == t2 and c2.nation == t1
                        and c1.source == c2.source
                        and c1.target == c2.target
                        and c1.n == c2.n):
                    vc1.union_status = "confirmed"
                    vc1.union_partner = t2
                    vc2.union_status = "confirmed"
                    vc2.union_partner = t1
                    matched.add(i)
                    matched.add(j)
                    break
            if i not in matched:
                vc1.union_status = "pending"

    def _resolve_union_attacks(self, vcmds: dict[str, list[ValidatedCmd]]):
        """
        Resolve union_attack coalitions using maximum-clique priority algorithm.

        For each target zone E:
        1. Find all valid coalitions (cliques: every member mutually lists all others)
        2. Pick the largest coalition; ties broken by highest total n (troops sent)
        3. Remove matched teams, recurse on remaining until none form valid coalitions
        4. Remaining teams attack independently (solo)
        """
        ua_by_target: dict[str, list[tuple[str, ParsedCommand, ValidatedCmd]]] = {}
        for team, vlist in vcmds.items():
            for vc in vlist:
                if vc.valid and vc.result.command and vc.result.command.op == "union_attack":
                    e = vc.result.command.target
                    ua_by_target.setdefault(e, []).append((team, vc.result.command, vc))

        for target, group in ua_by_target.items():
            # A team may have multiple commands to the same target (from different source
            # zones). Union ally-sets and sum troops across all of a team's commands so
            # that multi-source coalition attacks are resolved correctly.
            named: dict[str, set[str]] = {}
            troops_map: dict[str, int] = {}
            vcs_per_team: dict[str, list[ValidatedCmd]] = {}
            for t, cmd, vc in group:
                named.setdefault(t, set()).update(set(cmd.allies))
                troops_map[t] = troops_map.get(t, 0) + cmd.n
                vcs_per_team.setdefault(t, []).append(vc)

            assignment: dict[str, str] = {}
            remaining: set[str] = set(named.keys())
            cid_counter = 0

            while remaining:
                cliques = _find_all_cliques(remaining, named)
                if not cliques:
                    for t in remaining:
                        assignment[t] = f"solo_{t}"
                    break
                max_size = max(len(c) for c in cliques)
                candidates = [c for c in cliques if len(c) == max_size]
                winner = max(candidates,
                             key=lambda c: sum(troops_map.get(t, 0) for t in c))
                cid = f"C{cid_counter}"
                cid_counter += 1
                for t in winner:
                    assignment[t] = cid
                remaining -= winner

            coalition_members: dict[str, list[str]] = {}
            for t, cid in assignment.items():
                coalition_members.setdefault(cid, []).append(t)

            # Set effective_allies on ALL commands per team (multi-source support)
            for t, vcs in vcs_per_team.items():
                cid = assignment[t]
                allies = [m for m in coalition_members[cid] if m != t]
                for vc in vcs:
                    vc.effective_allies = allies


# ── Coalition helpers ─────────────────────────────────────────────────────────

def _find_all_cliques(
    teams: set[str],
    named: dict[str, set[str]],
) -> list[frozenset[str]]:
    """
    Return all valid coalitions of size >= 2 among `teams`.
    A coalition C is valid iff every member lists all other members in their P set.
    With at most 10 teams the 2^n enumeration is trivial.
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


# ── Round executor ────────────────────────────────────────────────────────────

def execute_round(
    state: GameState,
    vcmds: dict[str, list[ValidatedCmd]],
) -> tuple[GameState, list[str], list[dict]]:
    """
    Execute all valid commands for a round.
    Returns (new_state, log_lines, animation_events).

    animation_events: list of dicts used by the frontend real-mode animation.
      {"type":"move", "team":t, "from":zone, "to":zone, "n":int, "kind":op}
      {"type":"battle", "zone":z, "winner_teams":[t,...], "loser_teams":[t,...],
       "winner_total":int, "bonus":int}

    Execution order (as per rules):
    0. Apply admin set() commands
    1. Execute moving / attack / union / union_attack simultaneously
       (all read from round-start state, write to new state)
    2. Settle battles
    3. Produce national power from territories
    4. Settle neutral island
    5. Settle resource points
    """
    log = []
    anim: list[dict] = []  # animation events
    new_state = state.copy()

    # Record round-start zone owners BEFORE any operations
    # Used to ensure a 領主 with 0 troops still acts as nominal defender in Phase 2
    zone_start_owners: dict[str, Optional[str]] = {
        zone: zs.owner()
        for zone, zs in state.zones.items()
    }

    # Admin-only round: ADMIN has valid set commands AND no non-ADMIN team submitted anything.
    # Empty round (no commands at all) → normal round advance, not intermediate.
    # Determined before Phase 1 so battles are correctly skipped in admin-only rounds.
    # Phase 0 (admin set()) is deferred to after Phase 5 so team commands always execute
    # against the unmodified round-start state — preventing silent troop drops.
    _has_admin_cmds = any(vc.valid for vc in vcmds.get("ADMIN", []))
    _has_non_admin_input = any(
        len(vlist) > 0
        for team, vlist in vcmds.items()
        if team != "ADMIN"
    )
    _admin_only = _has_admin_cmds and not _has_non_admin_input

    # ── Phase 1: Simultaneous moves ───────────────────────────────────────
    # Read from state (start-of-round), accumulate deltas
    # delta_out[zone][team] = troops leaving zone
    # delta_in[zone][team] = troops arriving at zone
    # attacks[target] = list of (attacker_team, troops, coalition_id)
    #   where coalition_id is None for solo attack

    delta_out: dict[str, dict[str, int]] = {}
    delta_in: dict[str, dict[str, int]] = {}
    attacks: dict[str, list[dict]] = {}

    # Track zones whose troops are fully invalidated (conflict penalty)
    penalty_zones: dict[str, set[str]] = {}  # zone → set of teams
    conflict_penalized_amounts: dict[str, int] = {}  # team → troops forced to neutral (skip ×1.5)

    # First pass: find penalty zones (already marked invalid due to conflict)
    for team, vlist in vcmds.items():
        for vc in vlist:
            if not vc.valid and "兵力衝突" in vc.reason:
                # Extract zone from reason message
                # Find source zone from command (it's already parsed)
                if vc.result.command:
                    zone = vc.result.command.source
                    penalty_zones.setdefault(zone, set()).add(team)

    # Move troops out of penalty zones to neutral
    for zone, teams in penalty_zones.items():
        for team in teams:
            amount = state.zones[zone].troops.get(team, 0)
            if amount > 0:
                conflict_penalized_amounts[team] = conflict_penalized_amounts.get(team, 0) + amount
                delta_out.setdefault(zone, {})[team] = \
                    delta_out.get(zone, {}).get(team, 0) + amount
                # Move to neutral island
                delta_in.setdefault(NEUTRAL_ISLAND, {})[team] = \
                    delta_in.get(NEUTRAL_ISLAND, {}).get(team, 0) + amount
                log.append(
                    f"[衝突懲罰] {team} 隊在 {zone} 的 {amount} 兵力強制移入中立小島"
                )

    def add_delta_out(zone, team, n):
        delta_out.setdefault(zone, {}).setdefault(team, 0)
        delta_out[zone][team] += n

    def add_delta_in(zone, team, n):
        delta_in.setdefault(zone, {}).setdefault(team, 0)
        delta_in[zone][team] += n

    for team, vlist in vcmds.items():
        for vc in vlist:
            if not vc.valid:
                continue
            cmd = vc.result.command
            if cmd.op == "set":
                continue

            if cmd.op == "moving":
                add_delta_out(cmd.source, team, cmd.n)
                add_delta_in(cmd.target, team, cmd.n)
                log.append(f"{team}: moving({cmd.source} → {cmd.target}, {cmd.n})")
                anim.append({"type":"move","team":team,"from":cmd.source,
                              "to":cmd.target,"n":cmd.n,"kind":"moving"})

            elif cmd.op == "attack":
                add_delta_out(cmd.source, team, cmd.n)
                if cmd.target == NEUTRAL_ISLAND or cmd.target in RESOURCE_POINTS:
                    # Penalty attack: troops are lost, no battle at target
                    log.append(
                        f"[懲罰] {team}: attack→{cmd.target} 違反世界法，損失 {cmd.n} 兵力"
                    )
                    anim.append({"type":"move","team":team,"from":cmd.source,
                                  "to":cmd.target,"n":cmd.n,"kind":"penalty"})
                else:
                    attacks.setdefault(cmd.target, []).append({
                        "team": team,
                        "n": cmd.n,
                        "coalition": f"solo_{team}",
                    })
                    log.append(f"{team}: attack({cmd.source} → {cmd.target}, {cmd.n})")
                    anim.append({"type":"move","team":team,"from":cmd.source,
                                  "to":cmd.target,"n":cmd.n,"kind":"attack"})

            elif cmd.op == "union":
                if vc.union_status == "confirmed" and vc.union_role == "requesting":
                    # Only the requester actually moves troops
                    add_delta_out(cmd.source, team, cmd.n)
                    add_delta_in(cmd.target, team, cmd.n)
                    log.append(
                        f"{team}: union 成功（{vc.union_partner} 同意），"
                        f"{cmd.n} 兵力從 {cmd.source} 移至 {cmd.target}"
                    )
                    anim.append({"type":"move","team":team,"from":cmd.source,
                                  "to":cmd.target,"n":cmd.n,"kind":"union"})
                elif vc.union_status == "confirmed" and vc.union_role == "accepting":
                    log.append(
                        f"{team}: 接受 {vc.union_partner} 的 union 請求"
                    )
                else:
                    log.append(
                        f"{team}: union {cmd.source}→{cmd.target} 未配對，本回合無效"
                    )

            elif cmd.op == "union_attack":
                all_in_coalition = sorted([team] + vc.effective_allies)
                cid = "coa_" + "_".join(all_in_coalition) + "_" + cmd.target
                add_delta_out(cmd.source, team, cmd.n)
                if cmd.target == NEUTRAL_ISLAND or cmd.target in RESOURCE_POINTS:
                    # Penalty: all coalition members lose troops, no battle
                    log.append(
                        f"[懲罰] {team}: union_attack→{cmd.target} 違反世界法，損失 {cmd.n} 兵力"
                    )
                    anim.append({"type":"move","team":team,"from":cmd.source,
                                  "to":cmd.target,"n":cmd.n,"kind":"penalty"})
                else:
                    attacks.setdefault(cmd.target, []).append({
                        "team": team,
                        "n": cmd.n,
                        "coalition": cid,
                    })
                    allies_str = "+".join(vc.effective_allies) if vc.effective_allies else "solo"
                    log.append(
                        f"{team}: union_attack → {cmd.target}, "
                        f"盟友:{allies_str}, 出兵:{cmd.n}"
                    )
                    anim.append({"type":"move","team":team,"from":cmd.source,
                                  "to":cmd.target,"n":cmd.n,"kind":"union_attack",
                                  "allies":vc.effective_allies})

    # Apply delta_out (subtract from state into new_state)
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

    # ── Phase 2: Resolve battles ──────────────────────────────────────────
    if not _admin_only:
        for target, attacker_list in attacks.items():
            # ── Garrison betrayal detection ────────────────────────────────
            # If an attacking team already has troops at the target, those troops
            # are frozen (excluded from both attack and defence calculations).
            # Use pre-round state: §6.4 says "已有駐守兵力（先前 union 或戰役遺留）".
            # Troops that arrive at target via moving() in the SAME round are not garrison;
            # they arrive as fresh defenders (§7.6), not betrayal troops.
            garrison: dict[str, int] = {}  # team → n_Ac (frozen troops at target)
            for a in attacker_list:
                t = a["team"]
                n_ac = state.zones[target].troops.get(t, 0)
                if n_ac > 0:
                    garrison[t] = n_ac
    
            # ── Build coalition_troops ─────────────────────────────────────
            # Use += so a team sending from multiple zones sums into one entry.
            coalition_troops: dict[str, dict[str, int]] = {}
            for a in attacker_list:
                ct = coalition_troops.setdefault(a["coalition"], {})
                ct[a["team"]] = ct.get(a["team"], 0) + a["n"]
    
            # Defender = current zone troops MINUS frozen garrison
            raw_defender = dict(new_state.zones[target].troops)
            defender_troops = {t: n for t, n in raw_defender.items() if t not in garrison}

            # Ensure round-start 領主 is nominal defender even if they moved all troops away
            start_owner = zone_start_owners.get(target)
            if start_owner and start_owner not in garrison and start_owner not in defender_troops:
                defender_troops[start_owner] = 0

            if defender_troops:
                defender_cid = "defender"
                coalition_troops[defender_cid] = defender_troops
            else:
                defender_cid = None
    
            if not coalition_troops:
                continue
    
            # ── Tie-breaking battle loop ────────────────────────────────────
            # Iteratively eliminate equal-size tied attackers until a winner emerges.
            active = dict(coalition_troops)  # cid → {team: n}
            eliminated_troops: int = 0  # total troops from mutually-eliminated coalitions
    
            winner_cid: Optional[str] = None
            while True:
                totals = {cid: sum(tm.values()) for cid, tm in active.items()}
                if not totals:
                    break  # everyone eliminated
    
                max_total = max(totals.values())
                tied = [c for c, v in totals.items() if v == max_total]
    
                if len(tied) == 1:
                    winner_cid = tied[0]
                    break
    
                # Rule 1: defender wins ties
                if defender_cid in tied:
                    winner_cid = defender_cid
                    break
    
                # Rule 2: smallest coalition wins
                min_size = min(len(active[c]) for c in tied)
                smallest = [c for c in tied if len(active[c]) == min_size]
    
                if len(smallest) == 1:
                    winner_cid = smallest[0]
                    break
    
                # Rule 3: all equal-size tied → mutual elimination (no 20% bonus)
                for c in smallest:
                    eliminated_troops += totals[c]
                    del active[c]
                elim_str = ", ".join(
                    "+".join(coalition_troops[c]) for c in smallest
                )
                log.append(f"[戰鬥] {target}：同歸於盡（{elim_str}，各損失派遣兵力）")
    
            if winner_cid is None:
                # All attackers eliminated; defender (if any) survives unchanged
                if defender_cid:
                    new_zone = ZoneState(troops=dict(defender_troops))
                    new_zone.forced_owner = zone_start_owners.get(target)
                    new_state.zones[target] = new_zone
                else:
                    new_state.zones[target] = ZoneState(troops={})
                # Losing garrison → add n_Ac to loser pool for winner (no winner → lost)
                # (no winner exists here, garrison troops simply disappear)
                for t, n_ac in garrison.items():
                    log.append(f"[駐守叛變] {t} 駐守 n_Ac={n_ac} 隨攻方消滅")
                log.append(f"[戰鬥] {target}：攻方全滅，守方原地不動")
                continue
    
            winner_total = sum(active[winner_cid].values())

            # ── Garrison fate: split into winning / losing ─────────────────
            winning_garrison = {
                t: n_ac for t, n_ac in garrison.items()
                if t in active.get(winner_cid, {})
            }
            losing_garrison = {
                t: n_ac for t, n_ac in garrison.items()
                if t not in active.get(winner_cid, {})
            }

            # Sum all loser pools first, then apply single floor (§4.1).
            # Includes: active losers + mutually-eliminated troops + losing garrison n_Ae.
            # Excludes: winning garrison n_Ae (returned directly to A, not in pool).
            total_loser_pool = sum(
                sum(tm.values()) for c, tm in active.items() if c != winner_cid
            )
            total_loser_pool += eliminated_troops
            for _n in losing_garrison.values():
                total_loser_pool += _n
            bonus = math.floor(total_loser_pool * 0.20)

            # ── Build new zone troops ───────────────────────────────────────
            new_troops: dict[str, int] = {}

            # Each winner independently gets own troops + full bonus (§4.1)
            for t, n in active[winner_cid].items():
                new_troops[t] = n + bonus

            # Losers (still in active) lose all sent troops.
            # Teams that also appear in the winner coalition keep their winner-side troops.
            winner_teams = set(active[winner_cid].keys())
            for cid, tm in active.items():
                if cid == winner_cid:
                    continue
                for t in tm:
                    if t not in winner_teams:
                        new_troops[t] = 0

            # Winning garrison: n_Ac returned in full
            for t, n_ac in winning_garrison.items():
                new_troops[t] = new_troops.get(t, 0) + n_ac
                log.append(f"[駐守叛變] {t} 攻方獲勝，n_Ac={n_ac} 完整返還")

            # Losing garrison: included in per-coalition bonus above
            for t, n_ac in losing_garrison.items():
                log.append(f"[駐守叛變] {t} 攻方失敗，n_Ac={n_ac} 入敗方兵力池（已合算）")

            if losing_garrison:
                log.append(f"[駐守叛變] 勝方共獲 {bonus} 獎勵兵力（含駐守叛變）")

            # ── Determine new forced_owner (persists even at 0 troops, rule 1) ──
            if winner_cid == "defender":
                new_forced_owner = zone_start_owners.get(target)
            else:
                attack_forces = active[winner_cid]
                new_forced_owner = max(attack_forces, key=attack_forces.get) if attack_forces else None

            # Clean zeroes (garrison 0-troop = abandon; owner 0-troop stays via forced_owner)
            new_troops = {t: n for t, n in new_troops.items() if n > 0}
            new_zone = ZoneState(troops=new_troops)
            new_zone.forced_owner = new_forced_owner
            new_state.zones[target] = new_zone
    
            winners_str = "+".join(active[winner_cid].keys())
            losers = [c for c in active if c != winner_cid]
            losers_str = ", ".join("+".join(active[c].keys()) for c in losers)
            loser_teams = [t for c in losers for t in active[c].keys()]
            log.append(
                f"[戰鬥] {target}：{winners_str} 勝（{winner_total}兵），"
                f"獲得 {bonus} 獎勵兵力；失敗方：{losers_str or '無'}"
            )
            anim.append({
                "type": "battle",
                "zone": target,
                "winner_teams": list(active[winner_cid].keys()),
                "loser_teams": loser_teams,
                "winner_total": winner_total,
                "bonus": bonus,
            })
    
    if not _admin_only:
        # ── Phase 3: National power from territories ───────────────────────
        for zone in ISLANDS:
            x = TERRITORY_POWER.get(zone, 700)
            z_state = new_state.zones[zone]
            total_t = z_state.total()
            if total_t == 0:
                # 0 兵力但有佔領者（forced_owner）仍產出完整國力
                owner = z_state.owner()
                if owner:
                    new_state.national_power[owner] = \
                        new_state.national_power.get(owner, 0) + x
                    log.append(f"[國力] {zone}({x})：{owner} +{x}（0兵力領主）")
                continue

            owner = z_state.owner()

            # Include forced_owner even if they have 0 troops (cleaned from dict).
            # Per §4.2, the occupying lord always receives ½X as their base share.
            working_troops = dict(z_state.troops)
            if owner and owner not in working_troops:
                working_troops[owner] = 0

            if len(working_troops) == 1:
                team = next(iter(working_troops))
                new_state.national_power[team] = \
                    new_state.national_power.get(team, 0) + x
                log.append(f"[國力] {zone}({x})：{team} +{x}")
            else:
                half_x = x / 2
                gained = {}
                for team, troops in working_troops.items():
                    prop = troops / total_t
                    if owner is None:
                        # No forced owner: distribute full X proportionally
                        share = math.floor(x * prop)
                    elif team == owner:
                        share = math.floor(half_x + half_x * prop)
                    else:
                        share = math.floor(half_x * prop)
                    if share > 0:
                        gained[team] = share
                for team, share in gained.items():
                    new_state.national_power[team] = \
                        new_state.national_power.get(team, 0) + share
                log.append(
                    f"[國力] {zone}({x})：" +
                    ", ".join(f"{t}+{s}" for t, s in gained.items())
                )

        # ── Phase 4: Neutral island ────────────────────────────────────────
        neutral = new_state.zones[NEUTRAL_ISLAND]
        for team in list(neutral.troops.keys()):
            n = neutral.troops.get(team, 0)
            if n > 0:
                penalized_n = conflict_penalized_amounts.get(team, 0)
                legit_n = max(0, n - penalized_n)
                if legit_n == 0:
                    log.append(f"[中立] {team} 因衝突懲罰，本回合跳過中立小島 ×1.5")
                else:
                    new_n = math.floor(legit_n * 1.5) + penalized_n
                    neutral.troops[team] = new_n
                    if penalized_n > 0:
                        log.append(
                            f"[中立] {team} 兵力（{penalized_n} 衝突懲罰部分跳過，"
                            f"{legit_n} × 1.5）= {new_n}"
                        )
                    else:
                        log.append(f"[中立] {team} 兵力 {n} × 1.5 = {new_n}")

        # 0-troop relief (teams with no troops anywhere get 1000)
        for team in new_state.teams:
            total = new_state.total_troops(team)
            if total == 0:
                new_state.zones[NEUTRAL_ISLAND].troops[team] = \
                    new_state.zones[NEUTRAL_ISLAND].troops.get(team, 0) + 1000
                log.append(f"[救濟] {team} 兵力為 0，獲得 1000 兵力（中立小島）")

        # ── Phase 5: Resource points (unlocked from round 2) ──────────────
        if new_state.round >= 2:
            _settle_resource_points(new_state, log)

    # Advance round — or create intermediate sub-version for admin-only rounds
    if not _admin_only:
        # Normal round: advance round number, reset sub_round
        new_state.sub_round = 0
        new_state.round += 1
        if new_state.round > new_state.max_rounds:
            new_state.phase = "done"
        else:
            new_state.phase = "input"
    else:
        # Admin-only round: create intermediate sub-version X.1, X.2, ...
        new_state.sub_round = state.sub_round + 1
        new_state.phase = state.phase  # preserve current phase

    new_state.round_commands = {t: [] for t in new_state.teams}
    new_state.round_commands["ADMIN"] = []

    # Persist ownership: set forced_owner for zones not yet tracked (e.g. initial round)
    # so that 0-troop owners are recognized as nominal defenders in subsequent rounds.
    # BUG-17 fix: this block must run BEFORE Phase 0 admin set() so that an admin
    # set(K="") clearing forced_owner is not silently overridden by the persist block.
    for zone, zs in new_state.zones.items():
        if zs.forced_owner is None and zs.troops:
            by_t = sorted(zs.troops.items(), key=lambda kv: kv[1], reverse=True)
            if len(by_t) == 1 or by_t[0][1] > by_t[1][1]:
                new_state.zones[zone].forced_owner = by_t[0][0]

    # ── Phase 0: Admin set() (deferred — runs after all battles so team commands
    #    are never silently dropped due to admin troop-count changes mid-round) ──
    # BUG-17 fix: moved to after persist-ownership block so admin set(K="") can
    # override any ownership that was auto-assigned by the persist block above.
    for team, vlist in vcmds.items():
        for vc in vlist:
            if not vc.valid:
                continue
            cmd = vc.result.command
            if cmd.op == "set":
                zone = cmd.source
                new_troops: dict[str, int] = {}
                for t, n in cmd.allies:  # (team, troops) pairs
                    if n > 0:
                        new_troops[t] = n
                # cmd.nation == "\x00"  → K not provided, keep existing forced_owner
                # cmd.nation == ""      → K=0, clear forced_owner
                # cmd.nation == "1"-"10"→ set forced_owner to that team
                existing_fo = new_state.zones[zone].forced_owner
                if cmd.nation == "\x00":
                    fo = existing_fo  # unchanged
                elif cmd.nation == "":
                    fo = None  # clear
                else:
                    fo = cmd.nation  # set

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

    # Remove all 0-troop entries (garrison 0 = abandon; owner 0 preserved via forced_owner)
    for zs in new_state.zones.values():
        for team in [t for t, n in zs.troops.items() if n == 0]:
            del zs.troops[team]

    return new_state, log, anim


def _settle_resource_points(state: GameState, log: list[str]):
    """Settle 迷霧島, 金錢島, 漩渦 resource points."""
    # 迷霧島 R1: distribute 1000 troops proportionally
    r1 = state.zones.get("迷霧島")
    if r1 and r1.total() > 0:
        total_t = r1.total()
        bonus = 1000
        for team, troops in r1.troops.items():
            share = math.floor(bonus * troops / total_t)
            if share > 0:
                state.zones["迷霧島"].troops[team] = troops + share
                log.append(f"[迷霧島] {team} +{share} 兵力")

    # 金錢島 R2: distribute 1000 national power proportionally
    r2 = state.zones.get("金錢島")
    if r2 and r2.total() > 0:
        total_t = r2.total()
        bonus = 1000
        for team, troops in r2.troops.items():
            share = math.floor(bonus * troops / total_t)
            if share > 0:
                state.national_power[team] = state.national_power.get(team, 0) + share
                log.append(f"[金錢島] {team} +{share} 國力")

    # 漩渦 R3: depends on number of teams present
    r3 = state.zones.get("漩渦")
    if r3 and r3.total() > 0:
        team_count = len([t for t, n in r3.troops.items() if n > 0])
        if team_count == 4:
            log.append("[漩渦] 恰好 4 國，不產出")
        elif team_count % 2 == 0:
            # Even: 2000 troops
            total_t = r3.total()
            for team, troops in r3.troops.items():
                share = math.floor(2000 * troops / total_t)
                if share > 0:
                    state.zones["漩渦"].troops[team] = troops + share
                    log.append(f"[漩渦] 偶數國，{team} +{share} 兵力")
        else:
            # Odd: 2000 national power
            total_t = r3.total()
            for team, troops in r3.troops.items():
                share = math.floor(2000 * troops / total_t)
                if share > 0:
                    state.national_power[team] = \
                        state.national_power.get(team, 0) + share
                    log.append(f"[漩渦] 奇數國，{team} +{share} 國力")
