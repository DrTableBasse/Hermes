"""Transcriptions de tickets : tout texte venu de Discord est échappé (constat I1)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.transcript import message_block  # noqa: E402


def _block(**kw):
    base = dict(author="Camille#0001", display_name="Camille", is_bot=False,
                timestamp="01/01/2026 10:00:00", content="salut")
    return message_block(**{**base, **kw})


def test_initials_are_escaped():
    out = _block(display_name="<i")
    assert "<I" not in out and "&lt;I" in out


def test_attachment_url_cannot_break_out_of_href():
    out = _block(attachments=[('https://cdn.discordapp.com/x" onmouseover="alert(1)', "a.png")])
    assert '" onmouseover=' not in out
    assert "&quot; onmouseover=&quot;alert(1)" in out


def test_non_http_attachment_url_is_not_a_link():
    out = _block(attachments=[("javascript:alert(1)", "a.png")])
    assert "href" not in out and "a.png" in out


def test_content_embeds_and_author_are_escaped():
    out = _block(author="<script>", content="<img src=x onerror=1>",
                 embeds=[("<b>t", "<d>", [("<n>", "<v>")])])
    for raw in ("<script>", "<img", "<b>t", "<d>", "<n>", "<v>"):
        assert raw not in out
