"""Moteur pur des règles de rôles : conditions, plan de changements, conflits."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.role_rules import (  # noqa: E402
    CONDITIONS, MemberStats, Rule, find_conflicts, matches, plan_changes,
)

GRADES = {"sergent": 20, "caporal": 3}


def rule(id=1, ctype="messages", value="100", role_id=10, **kw):
    return Rule(id=id, condition_type=ctype, condition_value=value, role_id=role_id, **kw)


def test_conditions_closed_list():
    assert CONDITIONS == {"voice_hours", "messages", "level", "grade",
                          "achievement", "streak_days", "bumps", "invites"}


def test_matches_numeric_conditions_threshold():
    cases = [
        ("voice_hours", "100", {"voice_hours": 100.0}, {"voice_hours": 99.9}),
        ("messages", "50", {"messages": 50}, {"messages": 49}),
        ("level", "5", {"level": 5}, {"level": 4}),
        ("streak_days", "7", {"streak_days": 7}, {"streak_days": 6}),
        ("bumps", "3", {"bumps": 3}, {"bumps": 2}),
        ("invites", "2", {"invites": 2}, {"invites": 1}),
    ]
    for ctype, value, ok, ko in cases:
        r = rule(ctype=ctype, value=value)
        assert matches(r, MemberStats(**ok), GRADES) is True, ctype
        assert matches(r, MemberStats(**ko), GRADES) is False, ctype


def test_matches_grade_uses_level_min():
    r = rule(ctype="grade", value="sergent")
    assert matches(r, MemberStats(level=20), {"sergent": 20}) is True
    assert matches(r, MemberStats(level=19), {"sergent": 20}) is False
    assert matches(rule(ctype="grade", value="inconnu"), MemberStats(level=99), GRADES) is False


def test_matches_achievement():
    r = rule(ctype="achievement", value="7")
    assert matches(r, MemberStats(achievements=frozenset({7})), GRADES) is True
    assert matches(r, MemberStats(achievements=frozenset({8})), GRADES) is False


def test_plan_simple_add():
    add, rem = plan_changes([rule()], MemberStats(messages=100), set(), GRADES)
    assert add == {10} and rem == set()


def test_no_removal_without_remove_when_lost():
    add, rem = plan_changes([rule()], MemberStats(messages=1), {10}, GRADES)
    assert add == set() and rem == set()


def test_removal_with_remove_when_lost():
    r = rule(remove_when_lost=True)
    add, rem = plan_changes([r], MemberStats(messages=1), {10}, GRADES)
    assert add == set() and rem == {10}


def test_exclusive_group_keeps_highest_threshold():
    rules = [
        rule(id=1, ctype="level", value="5", role_id=10, exclusive_group="niv"),
        rule(id=2, ctype="level", value="10", role_id=20, exclusive_group="niv"),
    ]
    add, rem = plan_changes(rules, MemberStats(level=12), {10}, GRADES)
    assert add == {20}
    assert rem == {10}


def test_exclusive_group_not_added_when_only_lower_reached():
    rules = [
        rule(id=1, ctype="level", value="5", role_id=10, exclusive_group="niv"),
        rule(id=2, ctype="level", value="10", role_id=20, exclusive_group="niv"),
    ]
    add, rem = plan_changes(rules, MemberStats(level=6), {20}, GRADES)
    assert add == {10} and rem == {20}


def test_inactive_rule_ignored():
    r = rule(active=False, remove_when_lost=True)
    assert plan_changes([r], MemberStats(messages=500), set(), GRADES) == (set(), set())
    assert plan_changes([r], MemberStats(messages=0), {10}, GRADES) == (set(), set())


def test_rule_without_role_id_ignored():
    r = Rule(id=1, condition_type="achievement", condition_value="7",
             role_id=None, create_role_name="🏆 X")
    stats = MemberStats(achievements=frozenset({7}))
    assert plan_changes([r], stats, set(), GRADES) == (set(), set())


def test_find_conflicts_same_role_with_remove_when_lost():
    rules = [rule(id=1, role_id=10), rule(id=2, ctype="level", value="5",
                                          role_id=10, remove_when_lost=True)]
    assert len(find_conflicts(rules)) == 1


def test_find_conflicts_none_when_harmless():
    rules = [rule(id=1, role_id=10), rule(id=2, role_id=11, remove_when_lost=True),
             rule(id=3, role_id=10, active=False, remove_when_lost=True)]
    assert find_conflicts(rules) == []
