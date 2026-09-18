"""Two-stage safety filter: fast rules first, optional LLM classifier second.

Both stages are independent so tests can exercise rules without an LLM.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .interfaces import LLMProvider
from .models import Message, SafetyVerdict
from .prompts import SAFETY_CLASSIFIER_PROMPT

UNSAFE_CATEGORIES = {"violence", "sexual", "drugs", "self_harm", "personal_info", "hate", "scary", "other_unsafe"}


def _fold(text: str) -> str:
    """Lowercase and strip Vietnamese diacritics so 'giết' and 'giet' both match."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.replace("đ", "d")


# Keywords are matched as whole words. Keep these lists reviewable.
# _RULES_FOLDED: matched after stripping diacritics, so "giết" and "giet" both hit.
# _RULES_EXACT: matched with diacritics, for words whose folded form collides with
# innocent words ("tự tử" vs "từ từ", "bom" vs "bơm", "đấm" vs "đám", "súng" vs "sung sướng").
_RULES_FOLDED: dict[str, list[str]] = {
    "violence": ["giet", "chem", "dao gam", "danh nhau", "danh ban", "danh me", "danh em", "danh cho dau", "mau me", "kill", "gun", "knife", "bomb", "stab", "shoot"],
    "sexual": ["sex", "tinh duc", "khoa than", "porn", "lam tinh", "quan he tinh duc", "nude"],
    "drugs": ["ma tuy", "can sa", "heroin", "thuoc lac", "hut thuoc", "ruou bia", "say ruou", "cocaine", "weed", "vape"],
    "self_harm": ["tu sat", "muon chet", "tu lam dau", "cat tay", "suicide", "kill myself", "hurt myself"],
    "hate": ["do ngu", "dan toc thieu nang", "ky thi", "racist"],
    "scary": ["ma quy", "ac quy", "kinh di", "xac chet", "zombie", "horror", "ghost"],
}
_RULES_EXACT: dict[str, list[str]] = {
    "violence": ["súng", "bom", "đấm", "đâm"],
    "self_harm": ["tự tử"],
}

_PERSONAL_PATTERNS = [
    re.compile(r"\b(0|\+84)\d{8,10}\b"),  # VN phone numbers
    re.compile(r"\b(so dien thoai|dia chi nha|mat khau|password)\b"),
    re.compile(r"\b(nha (minh|em|con|to|tui|toi) o|em o so|nha em so)\b"),
]

_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF]")


def _word_hit(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


@dataclass
class RuleBasedSafetyFilter:
    """Cheap, deterministic, always on."""

    async def check_input(self, text: str) -> SafetyVerdict:
        return self.check(text)

    async def check_output(self, text: str) -> SafetyVerdict:
        return self.check(text)

    def check(self, text: str) -> SafetyVerdict:
        folded = _fold(text)
        lowered = text.lower()
        for pat in _PERSONAL_PATTERNS:
            if pat.search(folded):
                return SafetyVerdict(False, "personal_info", "rule:personal_pattern")
        for category, phrases in _RULES_FOLDED.items():
            for phrase in phrases:
                if _word_hit(folded, phrase):
                    return SafetyVerdict(False, category, f"rule:{phrase}")
        for category, phrases in _RULES_EXACT.items():
            for phrase in phrases:
                if _word_hit(lowered, phrase):
                    return SafetyVerdict(False, category, f"rule:{phrase}")
        return SafetyVerdict(True)


@dataclass
class LLMSafetyFilter:
    """Second stage: asks the LLM to classify. Fails open on transport errors so the
    conversation keeps working; rules already caught the obvious cases."""

    llm: LLMProvider

    async def _classify(self, text: str) -> SafetyVerdict:
        try:
            raw = await self.llm.complete(
                [Message("system", SAFETY_CLASSIFIER_PROMPT), Message("user", f"TEXT: {text}")],
                temperature=0.0,
                max_tokens=8,
            )
        except Exception as exc:  # noqa: BLE001
            return SafetyVerdict(True, "ok", f"llm_unavailable:{type(exc).__name__}")
        label = raw.strip().lower().split()[0].strip(".,") if raw.strip() else "ok"
        if label in UNSAFE_CATEGORIES:
            return SafetyVerdict(False, label, "llm")
        return SafetyVerdict(True)

    async def check_input(self, text: str) -> SafetyVerdict:
        return await self._classify(text)

    async def check_output(self, text: str) -> SafetyVerdict:
        return await self._classify(text)


@dataclass
class CompositeSafetyFilter:
    """Runs stages in order; first block wins. Output stages default to the input stages."""

    stages: list
    output_stages: list | None = None

    async def check_input(self, text: str) -> SafetyVerdict:
        for s in self.stages:
            v = await s.check_input(text)
            if not v.allowed:
                return v
        return SafetyVerdict(True)

    async def check_output(self, text: str) -> SafetyVerdict:
        for s in self.output_stages if self.output_stages is not None else self.stages:
            v = await s.check_output(text)
            if not v.allowed:
                return v
        return SafetyVerdict(True)


def sanitize_for_speech(text: str, max_chars: int) -> str:
    """Strip things a child should not hear or that TTS reads badly."""
    text = _URL.sub("", text)
    text = _EMOJI.sub("", text)
    text = re.sub(r"[*_#`>\[\]]", "", text)  # markdown leftovers
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        cut = text[:max_chars]
        # end on a sentence boundary when possible
        m = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
        text = cut[: m + 1] if m > max_chars // 2 else cut
    return text
