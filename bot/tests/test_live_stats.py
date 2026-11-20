"""Tests des calculs de la caserne en direct (module pur)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.live_stats import MemberView, MessageCounter, summarize  # noqa: E402

ROLES = {"lol": "League of Legends", "dbd": "Dead by Daylight"}


def test_counter_take_resets():
    c = MessageCounter()
    for _ in range(3):
        c.increment()
    assert c.take() == 3 and c.take() == 0


def test_counter_give_back():
    c = MessageCounter()
    c.increment()
    c.give_back(c.take())
    c.increment()
    assert c.take() == 2


def test_summarize_ignores_bots_and_counts():
    members = [
        MemberView(False, True, True, "a", frozenset({"League of Legends"})),
        MemberView(False, False, False, None, frozenset({"League of Legends", "Dead by Daylight"})),
        MemberView(True, True, True, "bot", frozenset({"League of Legends"})),
    ]
    r = summarize(members, ROLES)
    assert (r["members"], r["online"], r["in_voice"]) == (2, 1, 1)
    assert r["voice_avatars"] == ["a"] and r["game_players"] == {"lol": 2, "dbd": 1}


def test_summarize_avatar_limit_and_missing_avatar():
    members = [MemberView(False, True, True, f"u{i}") for i in range(8)]
    members.insert(0, MemberView(False, True, True, None))
    r = summarize(members, ROLES)
    assert r["in_voice"] == 9 and r["voice_avatars"] == ["u0", "u1", "u2", "u3", "u4"]


def test_summarize_empty():
    r = summarize([], ROLES)
    assert r["members"] == 0 and r["game_players"] == {"lol": 0, "dbd": 0}
