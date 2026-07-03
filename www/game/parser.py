"""
Command parser for 最終大戰 (COW).

Accepted commands:
  move(S, E, n)               -- move troops between own zones
  help(S, E, n, P)            -- send troops to ally P's island E (needs matching accept)
  accept(E, P)                -- authorize P to send troops to own island E
  attack(S, E, n)             -- solo attack (implicit [-1])
  attack(S, E, n, [P])        -- attack with optional ally list; [-1] = solo
  attack(S, E, n, [-1])       -- explicitly solo
  set(zone, K, T:n, ...)      -- admin: set zone state
  set(zone, T:n, ...)         -- admin: set troops without changing owner
  set(zone)                   -- admin: clear zone

Backward compat: `moving(S, E, n)` accepted as alias for `move`.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from .state import resolve_zone, ALL_TEAMS


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ParsedCommand:
    op: str            # "move" | "help" | "accept" | "attack" | "set"
    raw: str           # original text
    source: str = ""   # S zone (canonical)
    target: str = ""   # E zone (canonical)
    nation: str = ""   # P (for help/accept) — single team code
    allies: list = None  # [P, ...] for attack coalition; [] = solo
    n: int = 0

    def __post_init__(self):
        if self.allies is None:
            self.allies = []


@dataclass
class CommandResult:
    """Result of parsing a single line."""
    raw: str
    ok: bool
    command: Optional[ParsedCommand] = None
    error: str = ""


# ── Tokenizer ─────────────────────────────────────────────────────────────────

def _split_args(inner: str) -> list[str]:
    """
    Split arguments of a function call, respecting [...] brackets.
    Returns list of stripped arg strings.
    """
    args, depth, current = [], 0, []
    for ch in inner:
        if ch == '[':
            depth += 1
            current.append(ch)
        elif ch == ']':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            args.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        args.append(''.join(current).strip())
    return [a for a in args if a]


def _parse_allies(s: str) -> Optional[list[str]]:
    """
    Parse '[A,B,C]' or 'A' or '[-1]' or '-1' into a list of team codes.
    [-1] / -1 means solo → returns [].
    Returns None on failure.
    """
    s = s.strip()
    if s.startswith('[') and s.endswith(']'):
        inner = s[1:-1]
        items = [x.strip() for x in inner.split(',') if x.strip()]
    else:
        items = [s] if s else []

    result = []
    for item in items:
        if item == '-1':
            return []  # solo marker — discard all, return empty
        if item not in ALL_TEAMS:
            return None
        result.append(item)
    return result


def _parse_int(s: str) -> Optional[int]:
    try:
        v = int(s.strip())
        return v if v > 0 else None
    except ValueError:
        return None


def _parse_nonneg_int(s: str) -> Optional[int]:
    try:
        return int(s.strip())
    except ValueError:
        return None


# ── Main parser ───────────────────────────────────────────────────────────────

_OP_RE = re.compile(
    r'^\s*(move|moving|help|accept|union_attack|attack|union|set)\s*\(\s*(.*)\s*\)\s*$',
    re.DOTALL
)


def parse_command(line: str) -> CommandResult:
    raw = line.strip()
    if not raw:
        return CommandResult(raw=raw, ok=False, error="空行")

    normalized = re.sub(r'\s+', ' ', raw)

    m = _OP_RE.match(normalized)
    if not m:
        return CommandResult(raw=raw, ok=False, error="無法識別的指令格式")

    op = m.group(1)
    args = _split_args(m.group(2))

    if op in ("move", "moving"):
        return _parse_move(raw, args)
    elif op == "help":
        return _parse_help(raw, args)
    elif op == "accept":
        return _parse_accept(raw, args)
    elif op == "attack":
        return _parse_attack(raw, args)
    elif op == "union_attack":
        # Legacy alias: union_attack(S, [P], E, n) → attack(S, E, n, [P])
        return _parse_union_attack_alias(raw, args)
    elif op in ("union",):
        # Legacy alias: union(E, P) → accept(E, P)
        return _parse_accept(raw, args)
    elif op == "set":
        return _parse_set(raw, args)

    return CommandResult(raw=raw, ok=False, error="未知操作")


def _parse_move(raw: str, args: list[str]) -> CommandResult:
    if len(args) != 3:
        return CommandResult(raw=raw, ok=False,
                             error=f"move 需要 3 個參數，得到 {len(args)} 個")
    s = resolve_zone(args[0])
    e = resolve_zone(args[1])
    n = _parse_int(args[2])
    if s is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[0]!r}")
    if e is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[1]!r}")
    if n is None:
        return CommandResult(raw=raw, ok=False, error=f"兵力數必須為正整數：{args[2]!r}")
    return CommandResult(raw=raw, ok=True,
                         command=ParsedCommand(op="move", raw=raw, source=s, target=e, n=n))


def _parse_help(raw: str, args: list[str]) -> CommandResult:
    # help(S, E, n, P)
    if len(args) != 4:
        return CommandResult(raw=raw, ok=False,
                             error=f"help 需要 4 個參數 (S, E, n, P)，得到 {len(args)} 個")
    s = resolve_zone(args[0])
    e = resolve_zone(args[1])
    n = _parse_int(args[2])
    p = args[3].strip()
    if s is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[0]!r}")
    if e is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[1]!r}")
    if n is None:
        return CommandResult(raw=raw, ok=False, error=f"兵力數必須為正整數：{args[2]!r}")
    if p not in ALL_TEAMS:
        return CommandResult(raw=raw, ok=False, error=f"未知隊伍：{args[3]!r}")
    return CommandResult(raw=raw, ok=True,
                         command=ParsedCommand(op="help", raw=raw, source=s, target=e,
                                               nation=p, n=n))


def _parse_accept(raw: str, args: list[str]) -> CommandResult:
    # accept(E, P)
    if len(args) != 2:
        return CommandResult(raw=raw, ok=False,
                             error=f"accept 需要 2 個參數 (E, P)，得到 {len(args)} 個")
    e = resolve_zone(args[0])
    p = args[1].strip()
    if e is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[0]!r}")
    if p not in ALL_TEAMS:
        return CommandResult(raw=raw, ok=False, error=f"未知隊伍：{args[1]!r}")
    return CommandResult(raw=raw, ok=True,
                         command=ParsedCommand(op="accept", raw=raw, target=e, nation=p))


def _parse_attack(raw: str, args: list[str]) -> CommandResult:
    # attack(S, E, n)       → solo
    # attack(S, E, n, [P])  → with ally list; [-1] = solo
    if len(args) not in (3, 4):
        return CommandResult(raw=raw, ok=False,
                             error=f"attack 需要 3 或 4 個參數，得到 {len(args)} 個")
    s = resolve_zone(args[0])
    e = resolve_zone(args[1])
    n = _parse_int(args[2])
    if s is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[0]!r}")
    if e is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[1]!r}")
    if n is None:
        return CommandResult(raw=raw, ok=False, error=f"兵力數必須為正整數：{args[2]!r}")

    allies: list[str] = []
    if len(args) == 4:
        parsed = _parse_allies(args[3])
        if parsed is None:
            return CommandResult(raw=raw, ok=False,
                                 error=f"無效的盟友列表：{args[3]!r}")
        allies = parsed
    # Remove own team if accidentally included (will be caught in validation)
    return CommandResult(raw=raw, ok=True,
                         command=ParsedCommand(op="attack", raw=raw, source=s, target=e,
                                               allies=allies, n=n))


def _parse_union_attack_alias(raw: str, args: list[str]) -> CommandResult:
    # Legacy: union_attack(S, [P], E, n) → attack(S, E, n, [P])
    if len(args) != 4:
        return CommandResult(raw=raw, ok=False,
                             error=f"union_attack 需要 4 個參數 (S, [P], E, n)，得到 {len(args)} 個")
    s = resolve_zone(args[0])
    allies_raw = args[1]
    e = resolve_zone(args[2])
    n = _parse_int(args[3])
    if s is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[0]!r}")
    if e is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[2]!r}")
    if n is None:
        return CommandResult(raw=raw, ok=False, error=f"兵力數必須為正整數：{args[3]!r}")
    parsed_allies = _parse_allies(allies_raw)
    if parsed_allies is None:
        return CommandResult(raw=raw, ok=False, error=f"無效的盟友列表：{allies_raw!r}")
    return CommandResult(raw=raw, ok=True,
                         command=ParsedCommand(op="attack", raw=raw, source=s, target=e,
                                               allies=parsed_allies, n=n))


def _parse_set(raw: str, args: list[str]) -> CommandResult:
    # set(zone)                       → clear zone
    # set(zone, T:n, ...)             → set troops (forced_owner unchanged)
    # set(zone, K, T:n, ...)          → set troops + forced_owner = K (team or 0 to clear)
    if not args:
        return CommandResult(raw=raw, ok=False, error="set 至少需要 1 個參數（區域名稱）")
    zone = resolve_zone(args[0])
    if zone is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[0]!r}")

    rest = args[1:]
    forced_owner_str: Optional[str] = None

    if rest and ':' not in rest[0]:
        k = rest[0].strip()
        if k != '0' and k not in ALL_TEAMS:
            return CommandResult(raw=raw, ok=False,
                                 error=f"未知佔領國：{k!r}（應為隊伍號，或 0 表示清除）")
        forced_owner_str = "" if k == '0' else k
        rest = rest[1:]

    assignments: dict[str, int] = {}
    for spec in rest:
        if ':' not in spec:
            return CommandResult(raw=raw, ok=False,
                                 error=f"set 指令格式錯誤，每個分配應為 隊伍:兵力，得到 {spec!r}")
        team_s, n_s = spec.split(':', 1)
        team_s = team_s.strip()
        if team_s not in ALL_TEAMS:
            return CommandResult(raw=raw, ok=False, error=f"未知隊伍：{team_s!r}")
        n = _parse_nonneg_int(n_s)
        if n is None:
            return CommandResult(raw=raw, ok=False,
                                 error=f"兵力數必須為非負整數：{n_s!r}")
        assignments[team_s] = n

    cmd = ParsedCommand(op="set", raw=raw, source=zone,
                        nation=forced_owner_str if forced_owner_str is not None else "")
    cmd.allies = list(assignments.items())
    if forced_owner_str is None:
        cmd.nation = "\x00"  # sentinel: K not provided → leave forced_owner unchanged
    return CommandResult(raw=raw, ok=True, command=cmd)


# ── Multi-command parser ──────────────────────────────────────────────────────

_CMD_SCAN_RE = re.compile(r'\b(move|moving|help|accept|attack|union_attack|union|set)\b\s*\(')


def parse_commands(text: str) -> list[CommandResult]:
    """
    Parse a block of text into individual commands.
    Commands may be separated by any combination of newlines and/or spaces.
    Each command is scanned as keyword(...) with balanced parentheses.
    """
    results = []
    flat = re.sub(r'\s+', ' ', text).strip()

    pos = 0
    while pos < len(flat):
        m = _CMD_SCAN_RE.search(flat, pos)
        if not m:
            break
        cmd_start = m.start()
        paren_open = m.end() - 1
        depth = 0
        cmd_end = paren_open
        for j in range(paren_open, len(flat)):
            if flat[j] == '(':
                depth += 1
            elif flat[j] == ')':
                depth -= 1
                if depth == 0:
                    cmd_end = j
                    break
        else:
            results.append(CommandResult(
                raw=flat[cmd_start:].strip(), ok=False, error="括號不匹配"
            ))
            break
        results.append(parse_command(flat[cmd_start:cmd_end + 1]))
        pos = cmd_end + 1

    return results
