from json_response import stringify_big_ints, SnowflakeJSONResponse


def test_large_int_becomes_string():
    assert stringify_big_ints({"user_id": 1234567890123456789}) == {"user_id": "1234567890123456789"}


def test_small_int_and_bool_untouched():
    assert stringify_big_ints({"n": 42, "b": True, "f": 1.5}) == {"n": 42, "b": True, "f": 1.5}


def test_nested_lists():
    data = {"leaderboard": [{"user_id": 2**60, "xp": 10}]}
    assert stringify_big_ints(data)["leaderboard"][0] == {"user_id": str(2**60), "xp": 10}


def test_response_body():
    body = SnowflakeJSONResponse({"id": 2**60}).body
    assert body == b'{"id":"1152921504606846976"}'
