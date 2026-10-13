"""Validated extraction and normalization of Indonesian clinical numbers.

The rules are intentionally deterministic and independent of model output.
Percentages remain in percentage-point form (``15%`` becomes ``15``), while PES
codes are extracted separately from ordinary numbers.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

import yaml


NUMBER_VERSION = "numbers_v1.2"

PES_CODE_RE = re.compile(
    r"\b(?P<prefix>N[ICB])\s*[-.]?\s*"
    r"(?P<number>\d+(?:\s*\.\s*\d+)*)\b",
    re.IGNORECASE,
)

NUMBER_RE = re.compile(
    r"(?:(?<![A-Za-z0-9_])|(?<=\dx))"
    r"(?:(?P<sign>[+\-−])\s*)?"
    r"(?P<number>"
    r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+\.\d+|\d+(?:,\d+)?)"
    r")"
    r"(?P<percent>\s*(?:%|persen))?",
    re.IGNORECASE,
)

UNIT_RE = re.compile(
    r"^\s*(?P<unit>"
    r"kkal(?:\s*/\s*kg(?:BB)?(?:\s*/\s*(?:hari|hr))?)?|"
    r"kcal(?:\s*/\s*kg(?:BB)?(?:\s*/\s*(?:hari|hr))?)?|"
    r"mg\s*/\s*d[lL]|g\s*/\s*d[lL]|gr\s*/\s*d[lL]|"
    r"mmol\s*/\s*[lL]|mEq\s*/\s*[lL]|"
    r"10\s*\^\s*\d+\s*/\s*[uµμ][lL]|"
    r"kgBB|kg|gram|gr|g|cm|mm|mL|ml|liter|L|"
    r"SD|tahun|bulan|minggu|hari|jam"
    r")\b",
    re.IGNORECASE,
)

LIST_MARKER_RE = re.compile(
    r"(?m)^[ \t]*(?:[-*•]\s*)?(?P<number>\d{1,3})(?=[.)]\s+)"
)
PAREN_LIST_MARKER_RE = re.compile(
    r"(?m)^[ \t]*(?:[-*•]\s*)?\((?P<number>\d{1,3})\)(?=\s+)"
)
PAGE_LABEL_RE = re.compile(
    r"\b(?:halaman|hal\.?|page)\s*(?:ke[- ]?)?[:#-]?\s*"
    r"(?P<number>\d+)\b",
    re.IGNORECASE,
)
STANDALONE_PAGE_RE = re.compile(r"(?m)^[ \t]*(?P<number>\d{1,4})[ \t]*$")
SECTION_NUMBER_RE = re.compile(
    r"(?m)^[ \t]*(?P<number>\d+(?:\.\d+)+)"
    r"(?=\s+[A-ZÀ-ÖØ-Þ])"
)
CITATION_PAREN_YEAR_RE = re.compile(
    r"\((?=[^()\n]{0,120}\))[^()\n]*?"
    r"(?P<number>(?:19|20)\d{2})(?:[a-z])?(?=\s*\))",
    re.IGNORECASE,
)
CITATION_ORGANIZATION_YEAR_RE = re.compile(
    r"\b(?:Kemenkes|IDAI|WHO|Persagi|CDC|Permenkes|Depkes|UNICEF|ESPEN|ASPEN)"
    r"[^\d\n]{0,30}(?P<number>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
CITATION_YEAR_RE = re.compile(r"\b(?P<number>(?:19|20)\d{2})\b")

LAB_UNIT_RE = re.compile(
    r"^(?:mg/dl|g/dl|gr/dl|mmol/l|meq/l|10\^\d+/[uµμ]l)$",
    re.IGNORECASE,
)
LAB_TERM_RE = re.compile(
    r"hemoglobin|\bhb\b|albumin|natrium|kalium|leukosit|trombosit|"
    r"hematokrit|\bhct\b|\bmcv\b|\bmchc?\b|\bgds\b|sgot|sgpt|"
    r"kreatinin|ureum|glukosa",
    re.IGNORECASE,
)
ANTHROPOMETRY_RE = re.compile(
    r"z[ -]?score|simpang baku|standar deviasi|\bsd\b|imt|persentil|"
    r"bb/u|tb/u|pb/u|bb/tb|lila/u",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NumberConfig:
    relative_tolerance: Decimal = Decimal("0.005")
    absolute_tolerance: Decimal = Decimal("0.01")
    exclude_list_markers: bool = True
    exclude_labeled_page_numbers: bool = True
    exclude_standalone_page_numbers: bool = True
    exclude_section_numbers: bool = True
    exclude_citation_years: bool = True
    exclude_pes_components: bool = True


@dataclass(frozen=True)
class NumberMention:
    raw: str
    value: Decimal
    normalized: str
    start: int
    end: int
    unit: str | None
    category: str
    is_percent: bool

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["value"] = self.normalized
        return payload


@dataclass(frozen=True)
class PESCodeMention:
    raw: str
    normalized: str
    start: int
    end: int

    def to_dict(self) -> dict:
        return asdict(self)


def load_number_config(path: Path) -> NumberConfig:
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if raw["version"] != NUMBER_VERSION:
        raise ValueError(
            f"Unsupported numeric config version: {raw['version']!r}; "
            f"expected {NUMBER_VERSION!r}"
        )
    matching = raw["matching"]
    exclusions = raw["exclusions"]
    return NumberConfig(
        relative_tolerance=Decimal(str(matching["relative_tolerance"])),
        absolute_tolerance=Decimal(str(matching["absolute_tolerance"])),
        exclude_list_markers=bool(exclusions["list_markers"]),
        exclude_labeled_page_numbers=bool(exclusions["labeled_page_numbers"]),
        exclude_standalone_page_numbers=bool(exclusions["standalone_page_numbers"]),
        exclude_section_numbers=bool(exclusions["section_numbers"]),
        exclude_citation_years=bool(exclusions["citation_years"]),
        exclude_pes_components=bool(exclusions["pes_code_components"]),
    )


def canonical_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def normalize_number(raw: str) -> Decimal:
    """Normalize Indonesian numeric punctuation to a Decimal.

    A dot followed by exact three-digit groups is treated as a thousands
    separator (``1.500`` -> ``1500``). Other single-dot forms are decimal
    (``1.5`` -> ``1.5``). A comma is always decimal and dots before it are
    thousands separators (``1.705,8`` -> ``1705.8``).
    """

    value = raw.strip().replace(" ", "").replace("−", "-")
    if not value:
        raise ValueError("Cannot normalize an empty number")
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", value):
        value = value.replace(".", "")
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Invalid numeric token: {raw!r}") from error


def normalize_pes_code(raw: str) -> str:
    match = PES_CODE_RE.fullmatch(raw.strip())
    if not match:
        raise ValueError(f"Invalid PES code: {raw!r}")
    prefix = match.group("prefix").upper()
    components = [part.strip() for part in match.group("number").split(".")]
    return f"{prefix}-" + ".".join(components)


def extract_pes_codes(text: str) -> list[PESCodeMention]:
    return [
        PESCodeMention(
            raw=match.group(0),
            normalized=normalize_pes_code(match.group(0)),
            start=match.start(),
            end=match.end(),
        )
        for match in PES_CODE_RE.finditer(text)
    ]


def _group_spans(pattern: re.Pattern, text: str) -> list[tuple[int, int]]:
    return [match.span("number") for match in pattern.finditer(text)]


def _citation_year_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in CITATION_YEAR_RE.finditer(text):
        start, end = match.span("number")
        open_parenthesis = text.rfind("(", max(0, start - 160), start)
        close_parenthesis = text.find(")", end, min(len(text), end + 160))
        inside_parenthetical = (
            open_parenthesis != -1
            and close_parenthesis != -1
            and open_parenthesis < start < close_parenthesis
        )
        citation_prefix = text[max(0, start - 80) : start]
        preceded_by_citation_marker = bool(
            re.search(
                r"(?:,\s*|et\s+al\.?\s*,?\s*|"
                r"(?:Kemenkes|IDAI|WHO|Persagi|CDC|Permenkes|Depkes|UNICEF|"
                r"ESPEN|ASPEN)[^\d\n]{0,35})$",
                citation_prefix,
                re.IGNORECASE,
            )
        )
        if inside_parenthetical or preceded_by_citation_marker:
            spans.append((start, end))
    return spans


def exclusion_spans(text: str, config: NumberConfig) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    if config.exclude_pes_components:
        spans.extend((mention.start, mention.end) for mention in extract_pes_codes(text))
    if config.exclude_list_markers:
        spans.extend(_group_spans(LIST_MARKER_RE, text))
        spans.extend(_group_spans(PAREN_LIST_MARKER_RE, text))
    if config.exclude_labeled_page_numbers:
        spans.extend(_group_spans(PAGE_LABEL_RE, text))
    if config.exclude_standalone_page_numbers:
        spans.extend(_group_spans(STANDALONE_PAGE_RE, text))
    if config.exclude_section_numbers:
        spans.extend(_group_spans(SECTION_NUMBER_RE, text))
    if config.exclude_citation_years:
        spans.extend(_group_spans(CITATION_PAREN_YEAR_RE, text))
        spans.extend(_group_spans(CITATION_ORGANIZATION_YEAR_RE, text))
        spans.extend(_citation_year_spans(text))
    return sorted(spans)


def _overlaps(start: int, end: int, spans: Iterable[tuple[int, int]]) -> bool:
    return any(start < blocked_end and end > blocked_start for blocked_start, blocked_end in spans)


def _normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    compact = re.sub(r"\s+", "", unit)
    replacements = {"μ": "µ", "GR": "gr"}
    for source, target in replacements.items():
        compact = compact.replace(source, target)
    return compact


def categorize_number(
    text: str,
    *,
    start: int,
    end: int,
    unit: str | None,
    is_percent: bool,
) -> str:
    before = text[max(0, start - 45) : start]
    after = text[end : min(len(text), end + 45)]
    window = before + text[start:end] + after
    normalized_unit = (unit or "").replace(" ", "").casefold()

    if is_percent:
        return "percentage"
    if normalized_unit.startswith(("kkal", "kcal")) or re.search(
        r"(?:energi|kalori)\s*(?:=|sebesar|sebanyak)?\s*$", before, re.IGNORECASE
    ):
        return "energy"
    if LAB_UNIT_RE.fullmatch(normalized_unit) or LAB_TERM_RE.search(window):
        return "laboratory"
    if normalized_unit.casefold() == "sd" or ANTHROPOMETRY_RE.search(window):
        return "anthropometry_zscore"
    if normalized_unit in {"kg", "cm"} or re.search(
        r"(?:\bbb|\btb|berat badan|tinggi badan|lila|lingkar lengan)"
        r"\s*[:=]?\s*$",
        before,
        re.IGNORECASE,
    ):
        return "weight_height"
    return "other"


def extract_numbers(
    text: str, config: NumberConfig | None = None
) -> list[NumberMention]:
    config = config or NumberConfig()
    blocked = exclusion_spans(text, config)
    mentions: list[NumberMention] = []

    for match in NUMBER_RE.finditer(text):
        if _overlaps(match.start(), match.end(), blocked):
            continue
        sign = (match.group("sign") or "").replace("−", "-")
        # A hyphen immediately following a digit is a compact range separator,
        # not a negative sign: 136-145 -> 136 and 145.
        if sign == "-" and match.start() > 0:
            prefix = text[: match.start()].rstrip()
            if prefix and prefix[-1].isdigit():
                sign = ""
        numeric_raw = sign + match.group("number")
        value = normalize_number(numeric_raw)
        is_percent = match.group("percent") is not None

        unit: str | None = "%" if is_percent else None
        end = match.end()
        if not is_percent:
            unit_match = UNIT_RE.match(text[end:])
            if unit_match:
                unit = _normalize_unit(unit_match.group("unit"))
                end += unit_match.end()

        category = categorize_number(
            text,
            start=match.start(),
            end=end,
            unit=unit,
            is_percent=is_percent,
        )
        mentions.append(
            NumberMention(
                raw=text[match.start() : end],
                value=value,
                normalized=canonical_decimal(value),
                start=match.start(),
                end=end,
                unit=unit,
                category=category,
                is_percent=is_percent,
            )
        )
    return mentions


def has_number(text: str, config: NumberConfig | None = None) -> bool:
    return bool(extract_numbers(text, config))


def has_pes_code(text: str) -> bool:
    return bool(extract_pes_codes(text))


def numbers_match(
    left: Decimal | int | float | str,
    right: Decimal | int | float | str,
    config: NumberConfig | None = None,
) -> bool:
    config = config or NumberConfig()
    left_value = left if isinstance(left, Decimal) else Decimal(str(left))
    right_value = right if isinstance(right, Decimal) else Decimal(str(right))
    difference = abs(left_value - right_value)
    if difference <= config.absolute_tolerance:
        return True
    denominator = max(abs(left_value), abs(right_value))
    if denominator == 0:
        return True
    return difference / denominator <= config.relative_tolerance


def number_in_candidates(
    value: Decimal,
    candidates: Iterable[Decimal],
    config: NumberConfig | None = None,
) -> bool:
    return any(numbers_match(value, candidate, config) for candidate in candidates)

