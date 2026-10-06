"""
Deterministic bilingual (English / Persian) building-brief parser.

The parser normalises the brief in three passes before any pattern matching runs:

1. Persian and Arabic-Indic digits become ASCII digits.
2. Arabic letter variants and the zero-width non-joiner are folded to Persian forms.
3. Spelled-out numbers in both languages become digits.

After that a single set of regexes works for either language, so the patterns do
not depend on exact wording. Nothing here calls an LLM: an LLM may *pre-extract*
requirements, but this service is the deterministic floor that always runs.
"""

from __future__ import annotations

import re
import unicodedata

from app.domain.models.building_brief import (
    BriefLanguage,
    BuildingBrief,
    OccupancyKind,
    ParsedField,
)
from app.domain.models.pem_architecture import StructuralSystem

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_DIGIT_TRANSLATION = {
    **{ord(char): str(index) for index, char in enumerate(_PERSIAN_DIGITS)},
    **{ord(char): str(index) for index, char in enumerate(_ARABIC_INDIC_DIGITS)},
    ord("٫"): ".",
    ord("،"): ",",
    ord("\u200c"): " ",  # ZWNJ
    ord("\u200f"): " ",
    ord("\u200e"): " ",
    ord("ي"): "ی",
    ord("ك"): "ک",
    ord("ۀ"): "ه",
    ord("أ"): "ا",
    ord("إ"): "ا",
    ord("ؤ"): "و",
}

# Longest-first so "دوازده" is replaced before "دو".
_NUMBER_WORDS: dict[str, int] = {
    "یازده": 11,
    "دوازده": 12,
    "سیزده": 13,
    "چهارده": 14,
    "پانزده": 15,
    "شانزده": 16,
    "هفده": 17,
    "هجده": 18,
    "نوزده": 19,
    "بیست": 20,
    "یک": 1,
    "دو": 2,
    "سه": 3,
    "چهار": 4,
    "پنج": 5,
    "شش": 6,
    "شیش": 6,
    "هفت": 7,
    "هشت": 8,
    "نه": 9,
    "ده": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "single": 1,
}

_PERSIAN_RANGE = "\u0600-\u06FF"
_WORD_GUARD_LEFT = rf"(?<![0-9A-Za-z{_PERSIAN_RANGE}])"
_WORD_GUARD_RIGHT = rf"(?![0-9A-Za-z{_PERSIAN_RANGE}])"

_NUMBER = r"(\d+(?:[.,]\d+)?)"

_FLOOR_WORDS = r"(?:طبقه|طبقات|floors?|stor(?:y|ey|eys|ies)|levels?)"
_UNIT_WORDS = r"(?:واحد|واحدهای|apartments?|units?|flats?)"
_BEDROOM_WORDS = r"(?:خوابه?|خوابها|bed\s*rooms?|bedrooms?|beds?|br\b)"
# "3 residential floors" (English) and "3 طبقه مسکونی" (Persian) put the qualifier on
# opposite sides of the noun, so the qualifier is optional on both sides.
_FLOOR_QUALIFIER = r"(?:مسکونی|residential|typical|upper|apartment)"
_BATHROOM_WORDS = r"(?:حمام|سرویس\s*بهداشتی|سرویس|bath\s*rooms?|bathrooms?|baths?|wcs?|توالت)"
_PARKING_WORDS = r"(?:پارکینگ|پارکینگها|parking|car\s*parks?|carparks?|stalls?|cars?)"
_METRE_WORDS = r"(?:متر(?:ی)?|m(?:eters?|etres?)?\b|\u2032)"


class BuildingBriefParser:
    """Converts a free-text brief into a :class:`BuildingBrief`."""

    def parse(self, text: str) -> BuildingBrief:
        raw = text or ""
        language = self._detect_language(raw)
        normalized = self._normalize(raw)

        brief = BuildingBrief(raw_text=raw, language=language)
        fields: list[ParsedField] = []

        self._parse_plot(normalized, brief, fields)
        self._parse_frontage(normalized, brief, fields)
        self._parse_setbacks(normalized, brief, fields)
        self._parse_piloti(normalized, brief, fields)
        self._parse_parking(normalized, brief, fields)
        self._parse_floors(normalized, brief, fields)
        self._parse_apartments(normalized, brief, fields)
        self._parse_rooms(normalized, brief, fields)
        self._parse_circulation(normalized, brief, fields)
        self._parse_storey_height(normalized, brief, fields)
        self._parse_system_and_occupancy(normalized, brief, fields)

        brief.parsed_fields = fields
        brief.metadata["normalized_text"] = normalized
        return brief

    # -- normalisation ----------------------------------------------------

    @staticmethod
    def _normalize(text: str) -> str:
        folded = unicodedata.normalize("NFKC", text).translate(_DIGIT_TRANSLATION)
        lowered = folded.lower()
        for word, value in _NUMBER_WORDS.items():
            pattern = rf"{_WORD_GUARD_LEFT}{re.escape(word)}{_WORD_GUARD_RIGHT}"
            lowered = re.sub(pattern, str(value), lowered)
        return re.sub(r"\s+", " ", lowered).strip()

    @staticmethod
    def _detect_language(text: str) -> BriefLanguage:
        has_persian = bool(re.search(rf"[{_PERSIAN_RANGE}]", text))
        has_latin = bool(re.search(r"[A-Za-z]", text))
        if has_persian and has_latin:
            return BriefLanguage.MIXED
        if has_persian:
            return BriefLanguage.FA
        if has_latin:
            return BriefLanguage.EN
        return BriefLanguage.UNKNOWN

    @staticmethod
    def _to_float(raw: str) -> float:
        return float(raw.replace(",", "."))

    # -- individual requirements ------------------------------------------

    def _parse_plot(self, text: str, brief: BuildingBrief, fields: list[ParsedField]) -> None:
        # "12x22", "12 × 22", "12 در 22", "12 by 22", "12m x 22m"
        pattern = (
            rf"{_NUMBER}\s*{_METRE_WORDS}?\s*(?:[x×*]|در|by)\s*{_NUMBER}\s*{_METRE_WORDS}?"
        )
        match = re.search(pattern, text)
        if match is None:
            return
        first = self._to_float(match.group(1))
        second = self._to_float(match.group(2))
        if first <= 0 or second <= 0:
            return
        brief.plot_length_m = first
        brief.plot_width_m = second
        fields.append(
            ParsedField(
                field="plot_dimensions",
                value=f"{first} x {second}",
                matched_text=match.group(0).strip(),
                unit="m",
            )
        )

    def _parse_frontage(self, text: str, brief: BuildingBrief, fields: list[ParsedField]) -> None:
        patterns = (
            rf"(?:frontage|front\s*width)\s*(?:of|:|=)?\s*{_NUMBER}\s*{_METRE_WORDS}?",
            rf"{_NUMBER}\s*{_METRE_WORDS}?\s*(?:frontage|front\s*width)",
            rf"{_WORD_GUARD_LEFT}بر\s*(?:زمین|ملک)?\s*{_NUMBER}\s*{_METRE_WORDS}?",
            rf"{_NUMBER}\s*{_METRE_WORDS}\s*بر{_WORD_GUARD_RIGHT}",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match is None:
                continue
            value = self._to_float(match.group(1))
            if value <= 0:
                continue
            brief.frontage_m = value
            fields.append(
                ParsedField(
                    field="frontage",
                    value=str(value),
                    matched_text=match.group(0).strip(),
                    unit="m",
                )
            )
            return

    def _parse_setbacks(self, text: str, brief: BuildingBrief, fields: list[ParsedField]) -> None:
        specs = (
            ("setback_front_m", rf"(?:front\s*setback|عقب\s*نشینی\s*جلو)\s*(?:of|:|=)?\s*{_NUMBER}"),
            ("setback_rear_m", rf"(?:rear\s*setback|back\s*setback|عقب\s*نشینی\s*عقب)\s*(?:of|:|=)?\s*{_NUMBER}"),
            ("setback_side_m", rf"(?:side\s*setbacks?|عقب\s*نشینی\s*جانبی)\s*(?:of|:|=)?\s*{_NUMBER}"),
        )
        for attribute, pattern in specs:
            match = re.search(pattern, text)
            if match is None:
                continue
            value = self._to_float(match.group(1))
            if value < 0:
                continue
            setattr(brief, attribute, value)
            fields.append(
                ParsedField(
                    field=attribute,
                    value=str(value),
                    matched_text=match.group(0).strip(),
                    unit="m",
                )
            )

    def _parse_piloti(self, text: str, brief: BuildingBrief, fields: list[ParsedField]) -> None:
        pattern = (
            r"(پیلوت(?:ی)?|پیلوط|piloti|pilotis|pilot\s*floor|pilot\b"
            r"|parking\s*(?:floor|level|storey|story)"
            r"|طبقه\s*پارکینگ|همکف\s*پارکینگ"
            r"|ground\s*floor\s*parking)"
        )
        match = re.search(pattern, text)
        if match is None:
            return
        brief.has_piloti = True
        fields.append(
            ParsedField(field="has_piloti", value="true", matched_text=match.group(0).strip())
        )

    def _parse_parking(self, text: str, brief: BuildingBrief, fields: list[ParsedField]) -> None:
        patterns = (
            rf"{_NUMBER}\s*(?:عدد\s*)?{_PARKING_WORDS}",
            rf"{_PARKING_WORDS}\s*(?:spaces?|spots?|stalls?|برای)?\s*(?:for|:|=)?\s*{_NUMBER}",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match is None:
                continue
            count = int(float(match.group(1).replace(",", ".")))
            if count <= 0:
                continue
            brief.parking_space_count = count
            if not brief.has_piloti:
                brief.has_piloti = True
                fields.append(
                    ParsedField(
                        field="has_piloti",
                        value="true",
                        matched_text=f"implied by {match.group(0).strip()}",
                    )
                )
            fields.append(
                ParsedField(
                    field="parking_space_count",
                    value=str(count),
                    matched_text=match.group(0).strip(),
                )
            )
            return

    def _parse_floors(self, text: str, brief: BuildingBrief, fields: list[ParsedField]) -> None:
        candidates = (
            # "3 طبقه مسکونی" — qualifier follows the noun.
            rf"{_NUMBER}\s*{_FLOOR_WORDS}\s*(?:{_FLOOR_QUALIFIER}|of\s*apartments?)",
            # "3 residential floors" — qualifier precedes the noun.
            rf"{_NUMBER}\s*{_FLOOR_QUALIFIER}\s*{_FLOOR_WORDS}",
            rf"{_NUMBER}\s*{_FLOOR_WORDS}",
            rf"{_NUMBER}\s*[- ]?stor",
        )
        match = None
        for pattern in candidates:
            match = re.search(pattern, text)
            if match is not None:
                break
        if match is None:
            return
        count = int(float(match.group(1).replace(",", ".")))
        if count <= 0:
            return
        brief.residential_floor_count = count
        fields.append(
            ParsedField(
                field="residential_floor_count",
                value=str(count),
                matched_text=match.group(0).strip(),
            )
        )

    def _parse_apartments(self, text: str, brief: BuildingBrief, fields: list[ParsedField]) -> None:
        patterns = (
            rf"(?:هر\s*طبقه|per\s*floor|each\s*floor|in\s*each\s*floor)\s*{_NUMBER}\s*{_UNIT_WORDS}",
            rf"{_NUMBER}\s*{_UNIT_WORDS}\s*(?:در\s*)?(?:هر\s*طبقه|per\s*floor|each\s*floor|a\s*floor)",
            rf"{_NUMBER}\s*{_UNIT_WORDS}",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match is None:
                continue
            count = int(float(match.group(1).replace(",", ".")))
            if count <= 0:
                continue
            brief.apartments_per_floor = count
            fields.append(
                ParsedField(
                    field="apartments_per_floor",
                    value=str(count),
                    matched_text=match.group(0).strip(),
                )
            )
            return

    def _parse_rooms(self, text: str, brief: BuildingBrief, fields: list[ParsedField]) -> None:
        bedroom_match = re.search(rf"{_NUMBER}\s*{_BEDROOM_WORDS}", text)
        if bedroom_match is not None:
            count = int(float(bedroom_match.group(1).replace(",", ".")))
            if count > 0:
                brief.bedrooms_per_apartment = count
                fields.append(
                    ParsedField(
                        field="bedrooms_per_apartment",
                        value=str(count),
                        matched_text=bedroom_match.group(0).strip(),
                    )
                )

        bathroom_match = re.search(rf"{_NUMBER}\s*{_BATHROOM_WORDS}", text)
        if bathroom_match is not None:
            count = int(float(bathroom_match.group(1).replace(",", ".")))
            if count > 0:
                brief.bathrooms_per_apartment = count
                fields.append(
                    ParsedField(
                        field="bathrooms_per_apartment",
                        value=str(count),
                        matched_text=bathroom_match.group(0).strip(),
                    )
                )
        elif re.search(_BATHROOM_WORDS, text) is not None:
            brief.bathrooms_per_apartment = 1
            fields.append(
                ParsedField(field="bathrooms_per_apartment", value="1", matched_text="bathroom mentioned")
            )

        living_match = re.search(r"(living\s*rooms?|living|نشیمن|پذیرایی|هال|سالن)", text)
        if living_match is not None:
            brief.has_living_room = True
            fields.append(
                ParsedField(field="has_living_room", value="true", matched_text=living_match.group(0).strip())
            )

        kitchen_match = re.search(r"(kitchens?|آشپزخانه|آشپز)", text)
        if kitchen_match is not None:
            brief.has_kitchen = True
            fields.append(
                ParsedField(field="has_kitchen", value="true", matched_text=kitchen_match.group(0).strip())
            )

    def _parse_circulation(self, text: str, brief: BuildingBrief, fields: list[ParsedField]) -> None:
        stair_match = re.search(r"(stair\s*cases?|staircases?|stairs?|stairwell|راه\s*پله|راهپله|پله)", text)
        if stair_match is not None:
            brief.requires_stair = True
            fields.append(
                ParsedField(field="requires_stair", value="true", matched_text=stair_match.group(0).strip())
            )

        elevator_match = re.search(r"(elevators?|lifts?|آسانسور)", text)
        if elevator_match is not None:
            brief.requires_elevator = True
            fields.append(
                ParsedField(
                    field="requires_elevator", value="true", matched_text=elevator_match.group(0).strip()
                )
            )

    def _parse_storey_height(self, text: str, brief: BuildingBrief, fields: list[ParsedField]) -> None:
        pattern = (
            rf"(?:ارتفاع\s*(?:هر\s*)?طبقه|storey\s*height|story\s*height|floor\s*height"
            rf"|floor\s*to\s*floor)\s*(?:of|:|=)?\s*{_NUMBER}\s*{_METRE_WORDS}?"
        )
        match = re.search(pattern, text)
        if match is None:
            return
        value = self._to_float(match.group(1))
        if not 2.0 <= value <= 8.0:
            return
        brief.storey_height_m = value
        fields.append(
            ParsedField(
                field="storey_height_m",
                value=str(value),
                matched_text=match.group(0).strip(),
                unit="m",
            )
        )

    def _parse_system_and_occupancy(
        self,
        text: str,
        brief: BuildingBrief,
        fields: list[ParsedField],
    ) -> None:
        if re.search(r"(shear\s*walls?|دیوار\s*برشی|core\s*walls?)", text):
            brief.structural_system = StructuralSystem.RC_FRAME_WITH_SHEAR_WALLS
        elif re.search(r"(steel\s*frame|اسکلت\s*فلزی|فولادی|steel\s*structure)", text):
            brief.structural_system = StructuralSystem.STEEL_MOMENT_FRAME
        elif re.search(
            r"(reinforced\s*concrete|concrete\s*frame|rc\s*frame|بتن(?:ی|\s*آرمه)?|اسکلت\s*بتنی)",
            text,
        ):
            brief.structural_system = StructuralSystem.RC_MOMENT_FRAME
        if brief.structural_system is not StructuralSystem.UNDETERMINED:
            fields.append(
                ParsedField(field="structural_system", value=brief.structural_system.value, matched_text="")
            )

        residential = bool(
            re.search(r"(residential|مسکونی|apartments?|واحد)", text)
            or brief.bedrooms_per_apartment
            or brief.apartments_per_floor
        )
        if residential and brief.has_piloti:
            brief.occupancy = OccupancyKind.MIXED_USE
        elif residential:
            brief.occupancy = OccupancyKind.RESIDENTIAL
        elif brief.has_piloti or brief.parking_space_count:
            brief.occupancy = OccupancyKind.PARKING
