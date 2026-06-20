"""
Command parser for 最終大戰.

Accepted commands (spaces/newlines allowed freely except inside tokens):
  moving(S, E, n)
  attack(S, E, n)
  union(S, P, E, n)           -- P before E (consistent with union_attack)
  union_attack(S, P, E, n)   -- P can be [X,Y,...] or a single name
  set(zone, A:n, B:n, ...)   -- admin: set zone state
  set(zone)                  -- admin: clear zone
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from .state import resolve_zone, ALL_TEAMS


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ParsedCommand:
    op: str            # "moving" | "attack" | "union" | "union_attack" | "set"
    raw: str           # original text
    source: str = ""   # S zone (canonical)
    target: str = ""   # E zone (canonical)
    nation: str = ""   # P (for union) — single team letter
    allies: list = None  # [P, ...] (for union_attack)
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

# Strip whitespace, collapse inner whitespace in token positions
_WS = r'\s*'
_COMMA = r'\s*,\s*'

def _clean(s: str) -> str:
    """Remove leading/trailing whitespace."""
    return s.strip()


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
    Parse '[A,B,C]' or 'A' into a list of team letters.
    Returns None on failure.
    """
    s = s.strip()
    if s.startswith('[') and s.endswith(']'):
        inner = s[1:-1]
        items = [x.strip() for x in inner.split(',') if x.strip()]
    else:
        items = [s] if s else []
    for item in items:
        if item not in ALL_TEAMS:
            return None
    return items


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
    r'^\s*(moving|attack|union_attack|union|set)\s*\(\s*(.*)\s*\)\s*$',
    re.DOTALL
)


def parse_command(line: str) -> CommandResult:
    raw = line.strip()
    if not raw:
        return CommandResult(raw=raw, ok=False, error="空行")

    # Normalize whitespace inside the call (but preserve Chinese chars)
    normalized = re.sub(r'\s+', ' ', raw)

    m = _OP_RE.match(normalized)
    if not m:
        return CommandResult(raw=raw, ok=False, error="無法識別的指令格式")

    op = m.group(1)
    args = _split_args(m.group(2))

    if op == "moving":
        return _parse_moving(raw, args)
    elif op == "attack":
        return _parse_attack(raw, args)
    elif op == "union":
        return _parse_union(raw, args)
    elif op == "union_attack":
        return _parse_union_attack(raw, args)
    elif op == "set":
        return _parse_set(raw, args)

    return CommandResult(raw=raw, ok=False, error="未知操作")


def _parse_moving(raw: str, args: list[str]) -> CommandResult:
    if len(args) != 3:
        return CommandResult(raw=raw, ok=False,
                             error=f"moving 需要 3 個參數，得到 {len(args)} 個")
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
                         command=ParsedCommand(op="moving", raw=raw, source=s, target=e, n=n))


def _parse_attack(raw: str, args: list[str]) -> CommandResult:
    if len(args) != 3:
        return CommandResult(raw=raw, ok=False,
                             error=f"attack 需要 3 個參數，得到 {len(args)} 個")
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
                         command=ParsedCommand(op="attack", raw=raw, source=s, target=e, n=n))


def _parse_union(raw: str, args: list[str]) -> CommandResult:
    # union(S, P, E, n)  -- P before E (same order as union_attack)
    if len(args) != 4:
        return CommandResult(raw=raw, ok=False,
                             error=f"union 需要 4 個參數 (S, P, E, n)，得到 {len(args)} 個")
    s = resolve_zone(args[0])
    p = args[1].strip()
    e = resolve_zone(args[2])
    n = _parse_int(args[3])
    if s is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[0]!r}")
    if p not in ALL_TEAMS:
        return CommandResult(raw=raw, ok=False, error=f"未知隊伍：{args[1]!r}")
    if e is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[2]!r}")
    if n is None:
        return CommandResult(raw=raw, ok=False, error=f"兵力數必須為正整數：{args[3]!r}")
    return CommandResult(raw=raw, ok=True,
                         command=ParsedCommand(op="union", raw=raw, source=s, target=e,
                                               nation=p, n=n))


def _parse_union_attack(raw: str, args: list[str]) -> CommandResult:
    # union_attack(S, P, E, n)  -- P is [X,Y] or single X
    if len(args) != 4:
        return CommandResult(raw=raw, ok=False,
                             error=f"union_attack 需要 4 個參數 (S, P, E, n)，得到 {len(args)} 個")
    s = resolve_zone(args[0])
    allies = _parse_allies(args[1])
    e = resolve_zone(args[2])
    n = _parse_int(args[3])
    if s is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[0]!r}")
    if allies is None:
        return CommandResult(raw=raw, ok=False, error=f"無效的聯盟列表：{args[1]!r}")
    if not allies:
        return CommandResult(raw=raw, ok=False, error="聯盟列表不能為空")
    if e is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[2]!r}")
    if n is None:
        return CommandResult(raw=raw, ok=False, error=f"兵力數必須為正整數：{args[3]!r}")
    return CommandResult(raw=raw, ok=True,
                         command=ParsedCommand(op="union_attack", raw=raw, source=s,
                                               target=e, allies=allies, n=n))


def _parse_set(raw: str, args: list[str]) -> CommandResult:
    # set(zone)                  → clear
    # set(zone, A:100, B:200)   → assign
    if not args:
        return CommandResult(raw=raw, ok=False, error="set 至少需要 1 個參數（區域名稱）")
    zone = resolve_zone(args[0])
    if zone is None:
        return CommandResult(raw=raw, ok=False, error=f"未知區域：{args[0]!r}")
    assignments: dict[str, int] = {}
    for spec in args[1:]:
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
    cmd = ParsedCommand(op="set", raw=raw, source=zone)
    cmd.allies = list(assignments.items())  # reuse allies field as (team, n) pairs
    return CommandResult(raw=raw, ok=True, command=cmd)


# ── Multi-command parser ──────────────────────────────────────────────────────

# Matches the start of a command keyword followed by '('
_CMD_SCAN_RE = re.compile(r'\b(moving|union_attack|attack|union|set)\b\s*\(')


def parse_commands(text: str) -> list[CommandResult]:
    """
    Parse a block of text into individual commands.
    Commands may be separated by any combination of newlines and/or spaces.
    Each command is scanned as keyword(...) with balanced parentheses.
    """
    results = []
    # Collapse all whitespace runs to a single space for uniform scanning
    flat = re.sub(r'\s+', ' ', text).strip()

    pos = 0
    while pos < len(flat):
        m = _CMD_SCAN_RE.search(flat, pos)
        if not m:
            break
        cmd_start = m.start()
        paren_open = m.end() - 1  # index of '(' (the pattern ends with \()
        # Walk forward to find the matching closing paren
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
