"""
最終大戰 (WWW) — Flask application.

Usage:
    source venv/bin/activate
    python app.py
    → open http://localhost:5000
"""
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import copy
import threading

from game.state import GameState, ZoneState, ALL_ZONES, ALL_TEAMS
from game.parser import parse_commands
from game.engine import RoundValidator, execute_round

app = Flask(__name__)
CORS(app)

# ── Global game state ─────────────────────────────────────────────────────────
_state: GameState = GameState()
_history: list[GameState] = []  # undo stack
_future: list[GameState] = []   # redo stack (cleared on new execute)
_round_log: list[str] = []       # log from last execution
# BUG-14: single lock guards all reads/writes of _state, _history, _future, _round_log.
# Flask's threaded dev server and multi-worker WSGI servers can otherwise interleave
# concurrent requests and corrupt game state.
_state_lock = threading.Lock()


def _snapshot():
    """Save current state to undo history, clear redo stack.
    Caller must hold _state_lock.
    """
    _history.append(_state.copy())
    if len(_history) > 6:  # max 5 rounds + initial = 6
        _history.pop(0)
    _future.clear()


# ── Validation helper ─────────────────────────────────────────────────────────

def _validated_commands_dict():
    """
    Build and return validated commands for the current round.
    Returns: dict[team] → list of validated cmd dicts (serialisable).
    Caller must hold _state_lock (or be in a context where _state is stable).
    """
    parsed_by_team: dict = {}
    for team, raw_lines in _state.round_commands.items():
        results = []
        for raw in raw_lines:
            pr = parse_commands(raw)
            results.extend(pr)
        parsed_by_team[team] = results

    validator = RoundValidator(_state)
    vcmds = validator.validate_all(parsed_by_team)

    out = {}
    for team, vlist in vcmds.items():
        out[team] = []
        for vc in vlist:
            cmd = vc.result.command
            entry = {
                "raw": vc.result.raw,
                "parse_ok": vc.result.ok,
                "valid": vc.valid,
                "reason": vc.reason or vc.result.error,
                "warning": vc.warning,
                "op": cmd.op if cmd else None,
                "union_status": vc.union_status,
                "union_partner": vc.union_partner,
                "union_role": vc.union_role,
                "nation": cmd.nation if cmd and cmd.op == "union" else "",
                "effective_allies": vc.effective_allies,
            }
            out[team].append(entry)
    return out


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state", methods=["GET"])
def get_state():
    with _state_lock:
        return jsonify({
            "state": _state.to_dict(),
            "validated_commands": _validated_commands_dict(),
            "log": _round_log,
            "can_undo": len(_history) > 0,
            "can_redo": len(_future) > 0,
        })


@app.route("/api/setup", methods=["POST"])
def setup():
    """
    Initialize game before starting.
    Body: {
      "teams": ["A","B",...],          // which teams are playing
      "max_rounds": 3,                 // 1-5
      "territories": {                 // initial territory state
        "人類王國": {"A": 500, "B": 0},
        ...
      }
    }
    """
    global _state, _history, _round_log
    data = request.json or {}

    teams = data.get("teams", [str(i) for i in range(1, 11)])
    teams = [str(t) for t in teams if str(t) in ALL_TEAMS]
    if not teams:
        return jsonify({"error": "至少需要一支隊伍"}), 400

    max_rounds = int(data.get("max_rounds", 3))
    max_rounds = max(1, min(5, max_rounds))

    new_state = GameState(teams=teams, max_rounds=max_rounds)
    new_state.phase = "input"

    # Apply initial territories
    for zone_name, troops in (data.get("territories") or {}).items():
        from game.state import resolve_zone
        canonical = resolve_zone(zone_name)
        if canonical and canonical in new_state.zones:
            new_state.zones[canonical] = ZoneState(
                troops={t: int(n) for t, n in troops.items() if int(n) > 0}
            )

    # Apply initial national power if provided
    for team, power in (data.get("national_power") or {}).items():
        if team in new_state.teams:
            new_state.national_power[team] = int(power)

    with _state_lock:
        _state = new_state
        _history = []
        _future.clear()
        _round_log = []
        return jsonify({"ok": True, "state": _state.to_dict()})


@app.route("/api/commands/<team>", methods=["POST"])
def submit_commands(team):
    """
    Submit commands for a team this round.
    Body: {"text": "moving(...)\\nattack(...)"}
    Replaces any previous commands from this team this round.
    """
    with _state_lock:
        if team not in _state.teams and team != "ADMIN":
            return jsonify({"error": f"未知隊伍 {team}"}), 400
        if _state.phase not in ("input",):
            return jsonify({"error": "目前不在指令輸入階段"}), 400

        text = (request.json or {}).get("text", "")

        if team == "ADMIN":
            # Admin set commands accumulate across multiple submits
            if "ADMIN" not in _state.round_commands:
                _state.round_commands["ADMIN"] = []
            _state.round_commands["ADMIN"].append(text)
        else:
            _state.round_commands[team] = [text]

        return jsonify({
            "ok": True,
            "validated_commands": _validated_commands_dict(),
        })


@app.route("/api/commands/<team>", methods=["DELETE"])
def clear_commands(team):
    """Clear a team's commands for this round."""
    with _state_lock:
        if team in _state.round_commands:
            _state.round_commands[team] = [""]
        return jsonify({
            "ok": True,
            "validated_commands": _validated_commands_dict(),
        })


@app.route("/api/execute", methods=["POST"])
def execute():
    """Execute the current round."""
    global _state, _round_log
    with _state_lock:
        if _state.phase != "input":
            return jsonify({"error": "不在輸入階段，無法執行"}), 400

        # Parse all commands
        parsed_by_team: dict = {}
        for team, raw_lines in _state.round_commands.items():
            results = []
            for raw in raw_lines:
                pr = parse_commands(raw)
                results.extend(pr)
            parsed_by_team[team] = results

        validator = RoundValidator(_state)
        vcmds = validator.validate_all(parsed_by_team)

        _snapshot()

        new_state, log, anim = execute_round(_state, vcmds)
        _state = new_state
        _round_log = log

        return jsonify({
            "ok": True,
            "state": _state.to_dict(),
            "log": _round_log,
            "animation_events": anim,
        })


@app.route("/api/undo", methods=["POST"])
def undo():
    """Revert to previous non-intermediate state, skipping admin-only sub-versions."""
    global _state, _round_log
    with _state_lock:
        if not _history:
            return jsonify({"error": "沒有可回復的歷史"}), 400
        _future.append(_state.copy())
        _state = _history.pop()
        _round_log = []
        return jsonify({
            "ok": True, "state": _state.to_dict(),
            "can_undo": len(_history) > 0,
            "can_redo": len(_future) > 0,
        })


@app.route("/api/redo", methods=["POST"])
def redo():
    """Advance to next non-intermediate state (redo after undo), skipping sub-versions."""
    global _state, _round_log
    with _state_lock:
        if not _future:
            return jsonify({"error": "沒有可前進的回合"}), 400
        _history.append(_state.copy())
        _state = _future.pop()
        _round_log = []
        return jsonify({
            "ok": True, "state": _state.to_dict(),
            "can_undo": len(_history) > 0,
            "can_redo": len(_future) > 0,
        })


@app.route("/api/admin/set", methods=["POST"])
def admin_set():
    """
    Directly set zone state (admin use during game).
    Body: {"zone": "人類王國", "troops": {"A": 500, "B": 0}, "forced_owner": "A"}
    forced_owner is optional; omitting it preserves the existing value (BUG-15).
    """
    from game.state import resolve_zone
    data = request.json or {}
    zone = resolve_zone(data.get("zone", ""))
    if zone is None:
        return jsonify({"error": "未知區域"}), 400
    troops = {
        t: int(n)
        for t, n in (data.get("troops") or {}).items()
        if int(n) > 0
    }
    with _state_lock:
        # BUG-16: snapshot before modifying so undo can recover from admin-set operations
        _snapshot()

        # BUG-15: preserve existing forced_owner when caller does not supply one
        existing_fo = _state.zones[zone].forced_owner
        if "forced_owner" in data:
            fo = data["forced_owner"] or None  # explicit None/falsy clears it
        else:
            fo = existing_fo  # caller omitted the key — keep current value

        # BUG-18 fix: validate forced_owner against known teams to prevent spurious
        # keys from leaking into national_power dict in subsequent rounds.
        if fo is not None and fo not in _state.teams:
            return jsonify({"error": f"未知隊伍 {fo}"}), 400

        _state.zones[zone] = ZoneState(troops=troops, forced_owner=fo)
        return jsonify({"ok": True, "state": _state.to_dict()})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)
