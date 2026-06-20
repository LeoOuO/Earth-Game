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

        # ── Step 2: enforce 3-op limit per team ──────────────────────────
        for team, vlist in vcmds.items():
            ok_count = 0
            for vc in vlist:
                if vc.valid and vc.result.command and vc.result.command.op != "set":
                    ok_count += 1
                    if ok_count > 3:
                        vc.valid = False
                        vc.reason = "超過每回合 3 次操作上限"

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
            vc.valid = True  # admin commands always syntactically valid here
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
            if cmd.target == NEUTRAL_ISLAND or cmd.target in RESOURCE_POINTS:
                pass  # always movable
            elif not self._team_controls_zone(team, cmd.target):
                vc.valid = False
                vc.reason = f"moving 不可移動至他國領地 {cmd.target}"
                return vc
            if cmd.n > team_troops:
                vc.valid = False
                vc.reason = f"兵力不足：{cmd.source} 只有 {team_troops}，需要 {cmd.n}"
                return vc

        elif cmd.op == "attack":
            if not self._team_controls_zone(team, cmd.source):
                vc.valid = False
                vc.reason = f"{cmd.source} 不在己方控制下"
                return vc
            if cmd.target == NEUTRAL_ISLAND:
                vc.valid = False
                vc.reason = "不可進攻中立小島（中立小島不可被進攻）"
                return vc
            if self._team_owns_territory(team, cmd.target):
                vc.valid = False
                vc.reason = f"不可進攻己方領地 {cmd.target}"
                return vc
            if cmd.n > team_troops:
                vc.valid = False
                vc.reason = f"兵力不足：{cmd.source} 只有 {team_troops}，需要 {cmd.n}"
                return vc

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
                # Accepting mode: we are agreeing to host P's troops. No troop cost.
                vc.union_role = "accepting"
            elif is_p_territory:
                # Requesting mode: we move n troops from S to E (P's territory).
                vc.union_role = "requesting"
                if not self._team_controls_zone(team, cmd.source):
                    vc.valid = False
                    vc.reason = f"{cmd.source} 不在己方控制下（無法移動）"
                    return vc
                if cmd.n > team_troops:
                    vc.valid = False
                    vc.reason = f"兵力不足：{cmd.source} 只有 {team_troops}，需要 {cmd.n}"
                    return vc
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
            if cmd.target == NEUTRAL_ISLAND:
                vc.valid = False
                vc.reason = "不可進攻中立小島"
                return vc
            if self._team_owns_territory(team, cmd.target):
                vc.valid = False
                vc.reason = f"不可進攻己方領地 {cmd.target}"
                return vc
            if cmd.n > team_troops:
                vc.valid = False
                vc.reason = f"兵力不足：{cmd.source} 只有 {team_troops}，需要 {cmd.n}"
                return vc

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
            named: dict[str, set[str]] = {t: set(cmd.allies) for t, cmd, _ in group}
            troops_map: dict[str, int] = {t: cmd.n for t, cmd, _ in group}
            vc_map: dict[str, ValidatedCmd] = {t: vc for t, _, vc in group}

            assignment: dict[str, str] = {}
            remaining: set[str] = {t for t, _, _ in group}
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

            for t in (t for t, _, _ in group):
                cid = assignment[t]
                vc_map[t].effective_allies = [m for m in coalition_members[cid] if m != t]


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

    # ── Phase 0: Admin set() ───────────────────────────────────────────────
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
                new_state.zones[zone] = ZoneState(troops=new_troops)
                if new_troops:
                    summary = ", ".join(f"{t}:{n}" for t, n in new_troops.items())
                    log.append(f"[管理員] 設定 {zone}：{summary}")
                else:
                    log.append(f"[管理員] 清除 {zone}")

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
    for target, attacker_list in attacks.items():
        # Group by coalition
        coalition_troops: dict[str, dict[str, int]] = {}  # cid → {team: n}
        for a in attacker_list:
            coalition_troops.setdefault(a["coalition"], {})[a["team"]] = a["n"]

        # Include the current defender (from new_state after moves applied)
        defender_troops = dict(new_state.zones[target].troops)
        if defender_troops:
            defender_cid = "defender"
            coalition_troops[defender_cid] = defender_troops
        else:
            defender_cid = None

        # Sum troops per coalition
        totals: dict[str, int] = {
            cid: sum(troops.values())
            for cid, troops in coalition_troops.items()
        }

        if not totals:
            continue

        # Winner: coalition with most troops
        winner_cid = max(totals, key=lambda c: totals[c])
        winner_total = totals[winner_cid]

        # Tie check
        tied = [c for c, t in totals.items() if t == winner_total]
        if len(tied) > 1:
            # Defender wins ties
            if defender_cid in tied:
                winner_cid = defender_cid
            else:
                # Stable order: alphabetically first coalition
                winner_cid = min(tied)

        # Compute bonus: winner gets 20% of each loser's troops
        loser_total = sum(t for c, t in totals.items() if c != winner_cid)
        bonus = math.floor(loser_total * 0.20)

        # Build new zone state
        new_troops: dict[str, int] = {}
        for cid, team_troops_map in coalition_troops.items():
            if cid == winner_cid:
                # Add proportional bonus to each winner team
                for t, n in team_troops_map.items():
                    proportion = n / winner_total if winner_total > 0 else 0
                    new_troops[t] = n + math.floor(bonus * proportion)
            else:
                # Losers lose all sent troops
                for t in team_troops_map:
                    new_troops[t] = 0

        # Clean zeroes
        new_troops = {t: n for t, n in new_troops.items() if n > 0}
        new_state.zones[target] = ZoneState(troops=new_troops)

        winners_str = "+".join(coalition_troops[winner_cid].keys())
        losers = [c for c in totals if c != winner_cid]
        losers_str = ", ".join(
            "+".join(coalition_troops[c].keys()) for c in losers
        )
        loser_teams = [t for c in losers for t in coalition_troops[c].keys()]
        log.append(
            f"[戰鬥] {target}：{winners_str} 勝（{winner_total}兵），"
            f"獲得 {bonus} 獎勵兵力；失敗方：{losers_str}"
        )
        anim.append({
            "type": "battle",
            "zone": target,
            "winner_teams": list(coalition_troops[winner_cid].keys()),
            "loser_teams": loser_teams,
            "winner_total": winner_total,
            "bonus": bonus,
        })

    # ── Phase 3: National power from territories ──────────────────────────
    for zone in ISLANDS:
        x = TERRITORY_POWER.get(zone, 700)
        z_state = new_state.zones[zone]
        total_t = z_state.total()
        if total_t == 0:
            continue

        # Solo occupant
        if len(z_state.troops) == 1:
            team = next(iter(z_state.troops))
            new_state.national_power[team] = \
                new_state.national_power.get(team, 0) + x
            log.append(f"[國力] {zone}({x})：{team} +{x}")
        else:
            # Owner gets ½X + ½X * own_proportion; others get ½X * proportion
            owner = z_state.owner()
            half_x = x / 2
            gained = {}
            for team, troops in z_state.troops.items():
                prop = troops / total_t
                if team == owner:
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

    # ── Phase 4: Neutral island ───────────────────────────────────────────
    neutral = new_state.zones[NEUTRAL_ISLAND]
    for team in list(neutral.troops.keys()):
        n = neutral.troops.get(team, 0)
        if n > 0:
            new_n = math.floor(n * 1.5)
            neutral.troops[team] = new_n
            log.append(f"[中立] {team} 兵力 {n} × 1.5 = {new_n}")

    # 0-troop relief (teams with no troops anywhere get 1000)
    for team in new_state.teams:
        total = new_state.total_troops(team)
        if total == 0:
            new_state.zones[NEUTRAL_ISLAND].troops[team] = \
                new_state.zones[NEUTRAL_ISLAND].troops.get(team, 0) + 1000
            log.append(f"[救濟] {team} 兵力為 0，獲得 1000 兵力（中立小島）")

    # ── Phase 5: Resource points (unlocked from round 2) ─────────────────
    if new_state.round >= 2:
        _settle_resource_points(new_state, log)

    # Advance round
    new_state.round += 1
    if new_state.round > new_state.max_rounds:
        new_state.phase = "done"
    else:
        new_state.phase = "input"
    new_state.round_commands = {t: [] for t in new_state.teams}

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
