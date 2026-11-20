import database


def test_client_serves_health(client):
    assert client.get("/health").json() == {"status": "ok"}


async def test_fake_db_returns_programmed_result(fake_db):
    fake_db.on("from users", [{"user_id": 1}])
    assert await database.fetch("SELECT * FROM users") == [{"user_id": 1}]
    assert await database.fetchrow("SELECT 1") is None
    assert fake_db.calls[0][0] == "fetch"
