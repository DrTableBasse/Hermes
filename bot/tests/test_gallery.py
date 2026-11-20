"""Tests des fonctions pures de la galerie (aucune connexion Discord ni base)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.gallery import MAX_IMAGE_BYTES, accept_attachment, classify_clip, find_clip_url, sniff_image  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_sniff_png():
    assert sniff_image(PNG) == "png"


def test_sniff_other_formats():
    assert sniff_image(b"\xff\xd8\xff\xe0" + b"\x00" * 8) == "jpg"
    assert sniff_image(b"GIF89a" + b"\x00" * 8) == "gif"
    assert sniff_image(b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 4) == "webp"


def test_sniff_rejects_fake_png():
    assert sniff_image(b"<?php") is None
    assert sniff_image(b"") is None


def test_classify_clip_youtube():
    assert classify_clip("https://www.youtube.com/watch?v=abcdefghijk") == "youtube"
    assert classify_clip("https://youtu.be/abcdefghijk") == "youtube"


def test_classify_clip_twitch():
    assert classify_clip("https://clips.twitch.tv/FunnyClip") == "twitch"
    assert classify_clip("https://www.twitch.tv/saucisse/clip/FunnyClip") == "twitch"


def test_classify_clip_medal():
    assert classify_clip("https://medal.tv/games/dbd/clips/abc") == "medal"


def test_classify_clip_unknown():
    assert classify_clip("https://example.com") is None
    assert classify_clip("https://evil.com/?u=youtube.com/watch") is None
    assert classify_clip("https://youtube.com.evil.com/watch?v=1") is None


def test_find_clip_url_first_valid():
    text = "regardez https://example.com puis https://youtu.be/abcdefghijk et https://medal.tv/x"
    assert find_clip_url(text) == "https://www.youtube.com/watch?v=abcdefghijk"
    assert find_clip_url("rien ici") is None
    assert find_clip_url(None) is None


def test_oversize_rejected():
    assert accept_attachment(MAX_IMAGE_BYTES + 1, PNG) is False
    assert accept_attachment(len(PNG), PNG) is True
    assert accept_attachment(len(PNG), b"<?php") is False


def test_classify_rejects_backslash_bypass():
    assert classify_clip("https://evil.com\\@youtu.be/abcdefghijk") is None
    assert find_clip_url("https://evil.com\\@youtu.be/abcdefghijk") is None
    assert classify_clip("https://user@youtu.be/abcdefghijk") is None


def test_find_clip_url_rejects_quotes():
    assert find_clip_url("https://youtu.be/abcdefghijk\"onmouseover=1") is None
    assert find_clip_url("https://www.youtube.com/watch?v=abcdefghijk'x") is None


def test_clip_urls_are_canonical():
    assert find_clip_url("https://youtu.be/abcdefghijk?t=3") == "https://www.youtube.com/watch?v=abcdefghijk"
    assert find_clip_url("http://m.youtube.com/watch?v=abcdefghijk&list=x") == "https://www.youtube.com/watch?v=abcdefghijk"
    assert find_clip_url("https://www.twitch.tv/saucisse/clip/Funny-Clip_1?filter=x") == "https://clips.twitch.tv/Funny-Clip_1"
    assert find_clip_url("https://clips.twitch.tv/FunnyClip#a") == "https://clips.twitch.tv/FunnyClip"
    assert find_clip_url("https://medal.tv/games/dbd/clips/abc?x=1") == "https://medal.tv/games/dbd/clips/abc"
