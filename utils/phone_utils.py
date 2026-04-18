"""Phone extraction, normalization, and classification utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass


PHONE_CANDIDATE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?38)?0[\d\s\-\(\)]{8,16}\d(?!\d)"
)


@dataclass(frozen=True, slots=True)
class PhoneEntry:
    """Parsed phone information."""

    phone_raw: str
    phone_normalized: str | None
    phone_type: str


def extract_phone_candidates(text: str) -> list[str]:
    """Extract raw phone-like values from arbitrary text."""
    if not text:
        return []

    candidates = [match.group(0).strip() for match in PHONE_CANDIDATE_PATTERN.finditer(text)]
    return list(dict.fromkeys(candidates))


def normalize_ukrainian_phone(phone_raw: str) -> str | None:
    """Normalize Ukrainian phone to +380XXXXXXXXX format."""
    digits = re.sub(r"\D+", "", phone_raw or "")
    if not digits:
        return None

    if digits.startswith("380") and len(digits) == 12:
        normalized_digits = digits
    elif digits.startswith("0") and len(digits) == 10:
        normalized_digits = f"38{digits}"
    elif digits.startswith("80") and len(digits) == 11:
        normalized_digits = f"3{digits}"
    else:
        return None

    if not normalized_digits.startswith("380") or len(normalized_digits) != 12:
        return None
    return f"+{normalized_digits}"


def classify_ukrainian_phone(
    phone_normalized: str | None,
    mobile_prefixes: tuple[str, ...] | list[str],
) -> str:
    """Classify normalized phone as mobile, landline, or unknown."""
    if not phone_normalized:
        return "unknown"
    if not phone_normalized.startswith("+380") or len(phone_normalized) != 13:
        return "unknown"

    national_part = phone_normalized[4:]
    prefix2 = national_part[:2]
    prefix3 = national_part[:3]
    prefixes = set(mobile_prefixes)

    if prefix2 in prefixes or prefix3 in prefixes:
        return "mobile"
    return "landline"


def parse_phones_from_text(
    text: str,
    mobile_prefixes: tuple[str, ...] | list[str],
) -> list[PhoneEntry]:
    """Extract, normalize, classify, and deduplicate phones from text."""
    entries: list[PhoneEntry] = []
    seen_normalized: set[str | None] = set()

    for raw_phone in extract_phone_candidates(text):
        normalized = normalize_ukrainian_phone(raw_phone)
        phone_type = classify_ukrainian_phone(normalized, mobile_prefixes)
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        entries.append(
            PhoneEntry(
                phone_raw=raw_phone,
                phone_normalized=normalized,
                phone_type=phone_type,
            )
        )

    return entries


def extract_unique_phones(
    text: str,
    mobile_prefixes: tuple[str, ...] | list[str],
) -> list[str]:
    """Return unique normalized phones extracted from text."""
    unique_numbers: list[str] = []
    for entry in parse_phones_from_text(text, mobile_prefixes):
        if entry.phone_normalized:
            unique_numbers.append(entry.phone_normalized)
    return unique_numbers
