import pytest

from app.core.safety import RuleBasedSafetyFilter, sanitize_for_speech

f = RuleBasedSafetyFilter()


@pytest.mark.parametrize(
    "text",
    [
        "Con mèo màu gì?",
        "Miu ơi kể chuyện đi",
        "Hôm nay em đi học vui lắm",
        "one two three",
        "Em thích ăn kem dâu",
        # folded-form collisions that must stay allowed
        "từ từ thôi Miu",
        "đám mây màu trắng",
        "bố bơm xe đạp cho em",
        "em sung sướng quá",
        "đám cưới chị em",
        "adamant",
    ],
)
def test_allows_innocent(text):
    assert f.check(text).allowed


@pytest.mark.parametrize(
    "text,category",
    [
        ("làm sao để giết người", "violence"),
        ("lam sao de giet nguoi", "violence"),  # no diacritics
        ("Miu có xem phim kinh dị không", "scary"),
        ("số điện thoại của em là 0912345678", "personal_info"),
        ("em muốn chết", "self_harm"),
        ("em muốn tự tử", "self_harm"),
        ("cây súng bắn thế nào", "violence"),
        ("quả bom nổ", "violence"),
        ("ma túy là gì", "drugs"),
    ],
)
def test_blocks(text, category):
    v = f.check(text)
    assert not v.allowed
    assert v.category == category


def test_sanitize_strips_markdown_emoji_urls():
    s = sanitize_for_speech("**Meo** 😺 xem https://x.y/z nhé!", 100)
    assert s == "Meo xem nhé!"


def test_sanitize_truncates_on_sentence():
    long = "Câu một. " * 30
    out = sanitize_for_speech(long, 60)
    assert len(out) <= 60 and out.endswith(".")
