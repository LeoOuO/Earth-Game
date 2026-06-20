"""
Tests for the new union_attack coalition resolution algorithm.

Algorithm:
  1. Find all valid cliques (every member mutually lists all others in P)
  2. Pick the largest; tie-break by highest total troops (n)
  3. Remove matched teams, recurse until no cliques remain
  4. Remaining teams attack solo
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from game.engine import _find_all_cliques, RoundValidator
from game.state import GameState, ZoneState
from game.parser import parse_commands


# ─── _find_all_cliques unit tests ────────────────────────────────────────────

def test_find_cliques_full_triangle():
    """A,B,C all mutually list each other → {A,B,C} + three size-2 cliques."""
    teams = {"A", "B", "C"}
    named = {"A": {"B","C"}, "B": {"A","C"}, "C": {"A","B"}}
    cliques = set(_find_all_cliques(teams, named))
    assert frozenset({"A","B","C"}) in cliques
    assert frozenset({"A","B"}) in cliques
    assert frozenset({"A","C"}) in cliques
    assert frozenset({"B","C"}) in cliques
    print("PASS test_find_cliques_full_triangle")


def test_find_cliques_partial():
    """A=[B,C], B=[A], C=[A] → only {A,B} and {A,C}; no {B,C} or {A,B,C}."""
    teams = {"A","B","C"}
    named = {"A":{"B","C"}, "B":{"A"}, "C":{"A"}}
    cliques = set(_find_all_cliques(teams, named))
    assert frozenset({"A","B"}) in cliques
    assert frozenset({"A","C"}) in cliques
    assert frozenset({"B","C"}) not in cliques
    assert frozenset({"A","B","C"}) not in cliques
    print("PASS test_find_cliques_partial")


def test_find_cliques_chain_no_mutual():
    """A=[B], B=[C], C=[A] → zero mutual edges → no valid cliques."""
    teams = {"A","B","C"}
    named = {"A":{"B"}, "B":{"C"}, "C":{"A"}}
    assert _find_all_cliques(teams, named) == []
    print("PASS test_find_cliques_chain_no_mutual")


def test_find_cliques_solo():
    """Single team → no clique of size >= 2."""
    assert _find_all_cliques({"A"}, {"A":{"B"}}) == []
    print("PASS test_find_cliques_solo")


def test_find_cliques_four_way():
    """4 teams fully mutual → {A,B,C,D} is a valid clique."""
    teams = {"A","B","C","D"}
    named = {t: teams - {t} for t in teams}
    cliques = set(_find_all_cliques(teams, named))
    assert frozenset({"A","B","C","D"}) in cliques
    print("PASS test_find_cliques_four_way")


# ─── Integration helpers ──────────────────────────────────────────────────────

# Real zone names from the game
_ZONES = ["人類王國","精靈森域","龍族火山","獸人荒原","巨人山丘","侏儒劇場","狐族賭館"]

def make_state(attacker_teams, target_team):
    """
    Create a minimal GameState:
    - attacker_teams[i] owns _ZONES[i] with 500 troops each
    - target_team owns _ZONES[len(attacker_teams)] with 100 troops
    """
    all_teams = attacker_teams + [target_team]
    state = GameState(teams=all_teams)
    for i, t in enumerate(attacker_teams):
        state.zones[_ZONES[i]] = ZoneState(troops={t: 500})
    state.zones[_ZONES[len(attacker_teams)]] = ZoneState(troops={target_team: 100})
    return state


def resolve(state, commands_by_team: dict[str, str]) -> dict[str, list[str]]:
    """Parse and validate, return {team: sorted_effective_allies} for union_attack cmds."""
    parsed = {t: parse_commands(text) for t, text in commands_by_team.items()}
    vcmds = RoundValidator(state).validate_all(parsed)
    result = {}
    for team, vlist in vcmds.items():
        for vc in vlist:
            if vc.result.command and vc.result.command.op == "union_attack":
                if not vc.valid:
                    raise AssertionError(
                        f"team {team} union_attack unexpectedly invalid: {vc.reason}"
                    )
                result[team] = sorted(vc.effective_allies)
    return result


# ─── Integration tests ────────────────────────────────────────────────────────

def test_three_way_full_coalition():
    """1=[2,3], 2=[1,3], 3=[1,2] → all three in one coalition."""
    state = make_state(["1","2","3"], "4")
    allies = resolve(state, {
        "1": f"union_attack({_ZONES[0]}, [2,3], {_ZONES[3]}, 300)",
        "2": f"union_attack({_ZONES[1]}, [1,3], {_ZONES[3]}, 200)",
        "3": f"union_attack({_ZONES[2]}, [1,2], {_ZONES[3]}, 100)",
    })
    assert allies["1"] == ["2","3"], allies["1"]
    assert allies["2"] == ["1","3"], allies["2"]
    assert allies["3"] == ["1","2"], allies["3"]
    print("PASS test_three_way_full_coalition")


def test_partial_trust_ab_wins():
    """
    1=[2,3], 2=[1], 3=[1]. Valid cliques: {1,2} and {1,3}.
    Troops 1=300, 2=200, 3=100 → 1+2=500 > 1+3=400 → {1,2} wins, 3 solo.
    """
    state = make_state(["1","2","3"], "4")
    allies = resolve(state, {
        "1": f"union_attack({_ZONES[0]}, [2,3], {_ZONES[3]}, 300)",
        "2": f"union_attack({_ZONES[1]}, [1], {_ZONES[3]}, 200)",
        "3": f"union_attack({_ZONES[2]}, [1], {_ZONES[3]}, 100)",
    })
    assert allies["1"] == ["2"], allies["1"]
    assert allies["2"] == ["1"], allies["2"]
    assert allies["3"] == [],    allies["3"]
    print("PASS test_partial_trust_ab_wins")


def test_partial_trust_ac_wins():
    """
    1=[2,3], 2=[1], 3=[1]. Troops 1=100, 2=50, 3=200 → 1+3=300 > 1+2=150 → {1,3} wins.
    """
    state = make_state(["1","2","3"], "4")
    allies = resolve(state, {
        "1": f"union_attack({_ZONES[0]}, [2,3], {_ZONES[3]}, 100)",
        "2": f"union_attack({_ZONES[1]}, [1], {_ZONES[3]}, 50)",
        "3": f"union_attack({_ZONES[2]}, [1], {_ZONES[3]}, 200)",
    })
    assert allies["1"] == ["3"], allies["1"]
    assert allies["2"] == [],    allies["2"]
    assert allies["3"] == ["1"], allies["3"]
    print("PASS test_partial_trust_ac_wins")


def test_no_mutual_all_solo():
    """1=[2], 2=[3], 3=[1] → zero mutual edges → all solo."""
    state = make_state(["1","2","3"], "4")
    allies = resolve(state, {
        "1": f"union_attack({_ZONES[0]}, [2], {_ZONES[3]}, 300)",
        "2": f"union_attack({_ZONES[1]}, [3], {_ZONES[3]}, 300)",
        "3": f"union_attack({_ZONES[2]}, [1], {_ZONES[3]}, 300)",
    })
    assert allies["1"] == [], allies["1"]
    assert allies["2"] == [], allies["2"]
    assert allies["3"] == [], allies["3"]
    print("PASS test_no_mutual_all_solo")


def test_two_independent_three_way_coalitions():
    """
    1=[2,3], 2=[1,3], 3=[1,2] AND 4=[5,6], 5=[4,6], 6=[4,5] → two 3-way coalitions.
    Troops: 1+2+3=600, 4+5+6=300 → {1,2,3} wins first, then {4,5,6}.
    """
    state = make_state(["1","2","3","4","5","6"], "7")
    # Need to add team 7 manually since make_state only handles up to _ZONES[6]
    state2 = GameState(teams=["1","2","3","4","5","6","7"])
    for i, t in enumerate(["1","2","3","4","5","6"]):
        state2.zones[_ZONES[i]] = ZoneState(troops={t: 500})
    state2.zones["哥布林族"] = ZoneState(troops={"7": 100})

    allies = resolve(state2, {
        "1": f"union_attack({_ZONES[0]}, [2,3], 哥布林族, 300)",
        "2": f"union_attack({_ZONES[1]}, [1,3], 哥布林族, 200)",
        "3": f"union_attack({_ZONES[2]}, [1,2], 哥布林族, 100)",
        "4": f"union_attack({_ZONES[3]}, [5,6], 哥布林族, 150)",
        "5": f"union_attack({_ZONES[4]}, [4,6], 哥布林族, 100)",
        "6": f"union_attack({_ZONES[5]}, [4,5], 哥布林族, 50)",
    })
    assert sorted(allies["1"]) == ["2","3"], allies["1"]
    assert sorted(allies["2"]) == ["1","3"], allies["2"]
    assert sorted(allies["3"]) == ["1","2"], allies["3"]
    assert sorted(allies["4"]) == ["5","6"], allies["4"]
    assert sorted(allies["5"]) == ["4","6"], allies["5"]
    assert sorted(allies["6"]) == ["4","5"], allies["6"]
    print("PASS test_two_independent_three_way_coalitions")


def test_four_way_then_two_way_residual():
    """
    1,2,3,4 fully mutual → 4-way wins. 5=[6], 6=[5] → {5,6} forms in residual.
    """
    state = GameState(teams=["1","2","3","4","5","6","7"])
    for i, t in enumerate(["1","2","3","4","5","6"]):
        state.zones[_ZONES[i]] = ZoneState(troops={t: 500})
    state.zones["哥布林族"] = ZoneState(troops={"7": 100})

    allies = resolve(state, {
        "1": f"union_attack({_ZONES[0]}, [2,3,4], 哥布林族, 100)",
        "2": f"union_attack({_ZONES[1]}, [1,3,4], 哥布林族, 100)",
        "3": f"union_attack({_ZONES[2]}, [1,2,4], 哥布林族, 100)",
        "4": f"union_attack({_ZONES[3]}, [1,2,3], 哥布林族, 100)",
        "5": f"union_attack({_ZONES[4]}, [6], 哥布林族, 100)",
        "6": f"union_attack({_ZONES[5]}, [5], 哥布林族, 100)",
    })
    assert sorted(allies["1"]) == ["2","3","4"]
    assert sorted(allies["2"]) == ["1","3","4"]
    assert sorted(allies["3"]) == ["1","2","4"]
    assert sorted(allies["4"]) == ["1","2","3"]
    assert sorted(allies["5"]) == ["6"]
    assert sorted(allies["6"]) == ["5"]
    print("PASS test_four_way_then_two_way_residual")


def test_overlapping_max_cliques_troops_decide():
    """
    1=[2,3,4], 2=[1,3,4], 3=[1,2], 4=[1,2].
    Valid 3-way cliques: {1,2,3} (troops=600) and {1,2,4} (troops=650).
    {1,2,4} wins; 3 goes solo.
    """
    state = make_state(["1","2","3","4"], "5")
    allies = resolve(state, {
        "1": f"union_attack({_ZONES[0]}, [2,3,4], {_ZONES[4]}, 300)",
        "2": f"union_attack({_ZONES[1]}, [1,3,4], {_ZONES[4]}, 200)",
        "3": f"union_attack({_ZONES[2]}, [1,2], {_ZONES[4]}, 100)",
        "4": f"union_attack({_ZONES[3]}, [1,2], {_ZONES[4]}, 150)",
    })
    assert sorted(allies["1"]) == ["2","4"], f"1: {allies['1']}"
    assert sorted(allies["2"]) == ["1","4"], f"2: {allies['2']}"
    assert allies["3"] == [],                f"3 should be solo: {allies['3']}"
    assert sorted(allies["4"]) == ["1","2"], f"4: {allies['4']}"
    print("PASS test_overlapping_max_cliques_troops_decide")


def test_single_attacker_no_partner_solo():
    """Only one attacker, target owned by defender. Attacker goes solo."""
    state = make_state(["1"], "2")
    allies = resolve(state, {
        "1": f"union_attack({_ZONES[0]}, [2], {_ZONES[1]}, 200)",
    })
    # team 2 is defender, not attacker → no pair → 1 is solo
    assert allies.get("1", []) == [], f"1 should be solo: {allies.get('1')}"
    print("PASS test_single_attacker_no_partner_solo")


def test_three_attackers_one_pair_one_solo():
    """1=[2], 2=[1], 3=[1] → {1,2} valid (mutual), 3 lists 1 but 1 doesn't list 3 → 3 solo."""
    state = make_state(["1","2","3"], "4")
    allies = resolve(state, {
        "1": f"union_attack({_ZONES[0]}, [2], {_ZONES[3]}, 300)",
        "2": f"union_attack({_ZONES[1]}, [1], {_ZONES[3]}, 200)",
        "3": f"union_attack({_ZONES[2]}, [1], {_ZONES[3]}, 100)",
    })
    assert allies["1"] == ["2"], f"1: {allies['1']}"
    assert allies["2"] == ["1"], f"2: {allies['2']}"
    assert allies["3"] == [],    f"3 should be solo: {allies['3']}"
    print("PASS test_three_attackers_one_pair_one_solo")


# ─── Run all ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_find_cliques_full_triangle,
        test_find_cliques_partial,
        test_find_cliques_chain_no_mutual,
        test_find_cliques_solo,
        test_find_cliques_four_way,
        test_three_way_full_coalition,
        test_partial_trust_ab_wins,
        test_partial_trust_ac_wins,
        test_no_mutual_all_solo,
        test_two_independent_three_way_coalitions,
        test_four_way_then_two_way_residual,
        test_overlapping_max_cliques_troops_decide,
        test_single_attacker_no_partner_solo,
        test_three_attackers_one_pair_one_solo,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"FAIL {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{passed+failed} PASSED")
    if failed:
        sys.exit(1)
