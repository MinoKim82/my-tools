from datetime import datetime, timezone
import pytest
from main import chunk_text, parse_relative_or_absolute_time


def test_time_parser_relative():
    tz = timezone.utc
    now = datetime.now(tz)

    t_now = parse_relative_or_absolute_time("now", tz)
    assert abs((t_now - now).total_seconds()) < 2

    t_2h = parse_relative_or_absolute_time("2h", tz)
    diff_h = (now - t_2h).total_seconds() / 3600
    assert 1.99 < diff_h < 2.01

    t_3d = parse_relative_or_absolute_time("3d", tz)
    diff_d = (now - t_3d).total_seconds() / 86400
    assert 2.99 < diff_d < 3.01


def test_time_parser_absolute():
    tz = timezone.utc
    dt = parse_relative_or_absolute_time("2026-09-20 12:30", tz)
    assert dt.year == 2026
    assert dt.month == 9
    assert dt.day == 20
    assert dt.hour == 12
    assert dt.minute == 30


def test_chunk_text():
    short = "Hello Telegram"
    assert chunk_text(short, max_len=100) == [short]

    long_text = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
    chunks = chunk_text(long_text, max_len=15)
    assert len(chunks) == 3
    assert chunks[0] == "Paragraph 1"
    assert chunks[1] == "Paragraph 2"
    assert chunks[2] == "Paragraph 3"
