"""Temporisation après un refus de création de salon (horloge injectée)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.settings_backoff import CreationBackoff  # noqa: E402


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_not_blocked_by_default():
    assert CreationBackoff(clock=FakeClock()).is_blocked("log_channel") is False


def test_blocked_for_ten_minutes_after_forbidden():
    clock = FakeClock()
    backoff = CreationBackoff(clock=clock)
    backoff.block("log_channel")
    clock.now += 599
    assert backoff.is_blocked("log_channel") is True
    clock.now += 1
    assert backoff.is_blocked("log_channel") is False


def test_block_is_per_key():
    backoff = CreationBackoff(clock=FakeClock())
    backoff.block("log_channel")
    assert backoff.is_blocked("voice_log_channel") is False


def test_clear_lifts_block():
    backoff = CreationBackoff(clock=FakeClock())
    backoff.block("log_channel")
    backoff.clear()
    assert backoff.is_blocked("log_channel") is False
