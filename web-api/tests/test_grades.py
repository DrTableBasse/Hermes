import pytest

import grades
from grades import DEFAULT_GRADES, grade_for_level

GRADES = DEFAULT_GRADES


@pytest.fixture(autouse=True)
def _fresh_cache():
    grades.clear_grades_cache()
    yield
    grades.clear_grades_cache()


@pytest.mark.parametrize("level,slug", [(0, "recrue"), (1, "recrue"), (2, "recrue"), (3, "caporal"),
    (7, "caporal"), (8, "sergent"), (14, "sergent"), (15, "lieutenant"), (24, "lieutenant"),
    (25, "colonel"), (44, "colonel"), (45, "general"), (200, "general")])
def test_grade_bounds(level, slug):
    assert grade_for_level(level, GRADES)["slug"] == slug


def test_get_grades_route(client, fake_db):
    fake_db.on("FROM grades", GRADES)
    r = client.get("/grades")
    assert r.status_code == 200 and [g["slug"] for g in r.json()["grades"]][0] == "recrue"


def test_get_grades_is_cached(client, fake_db):
    fake_db.on("FROM grades", GRADES)
    client.get("/grades")
    client.get("/grades")
    assert len([c for c in fake_db.calls if "from grades" in c[1].lower()]) == 1
    grades.clear_grades_cache()
    client.get("/grades")
    assert len([c for c in fake_db.calls if "from grades" in c[1].lower()]) == 2


def test_public_profile_has_grade(client, fake_db):
    fake_db.on("FROM grades", GRADES)
    fake_db.on("SELECT user_id, username, nickname", {"user_id": 5, "username": "u", "nickname": None,
                                                      "discord_avatar": None})
    fake_db.on("SELECT total_xp, current_level FROM user_xp", {"total_xp": 900, "current_level": 9})
    r = client.get("/users/5/public")
    assert r.status_code == 200
    assert r.json()["stats"]["grade"]["slug"] == "sergent"
    assert set(r.json()["stats"]["grade"]) == {"name", "slug", "color"}


def test_leaderboard_levels_has_grade_per_entry(client, fake_db):
    fake_db.on("FROM grades", GRADES)
    fake_db.on("FROM user_xp x", [
        {"user_id": 1, "username": "a", "discord_avatar": None, "current_level": 50, "total_xp": 9, "global_rank": 1},
        {"user_id": 2, "username": "b", "discord_avatar": None, "current_level": 2, "total_xp": 1, "global_rank": 2}])
    r = client.get("/leaderboard/levels")
    assert [e["grade"]["slug"] for e in r.json()["leaderboard"]] == ["general", "recrue"]
    assert len([c for c in fake_db.calls if "from grades" in c[1].lower()]) == 1


def test_xp_user_has_grade(client, fake_db):
    fake_db.on("FROM grades", GRADES)
    fake_db.on("FROM user_xp WHERE", {"user_id": 7, "total_xp": 5, "weekly_xp": 1, "current_level": 3})
    assert client.get("/xp/7").json()["grade"]["slug"] == "caporal"
    fake_db.rules.clear()
    fake_db.on("FROM grades", GRADES)
    assert client.get("/xp/8").json()["grade"]["slug"] == "recrue"


def test_empty_table_falls_back(client, fake_db, caplog):
    fake_db.on("FROM grades", [])
    r = client.get("/grades")
    assert r.status_code == 200 and len(r.json()["grades"]) == 6
    assert "Table grades vide" in caplog.text


def test_empty_not_cached(client, fake_db):
    fake_db.on("FROM grades", [])
    client.get("/grades")
    fake_db.rules.clear()
    fake_db.on("FROM grades", [{"level_min": 1, "name": "X", "slug": "x", "color": "#000"}])
    assert [g["slug"] for g in client.get("/grades").json()["grades"]] == ["x"]


def test_null_level(client, fake_db):
    fake_db.on("FROM grades", GRADES)
    fake_db.on("FROM user_xp WHERE", {"user_id": 7, "total_xp": 0, "weekly_xp": 0, "current_level": None})
    assert client.get("/xp/7").json()["grade"]["slug"] == "recrue"
    assert grade_for_level(None, GRADES)["slug"] == "recrue"
