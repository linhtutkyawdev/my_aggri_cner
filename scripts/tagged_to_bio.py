#!/usr/bin/env python3
"""Convert `token@TAG|` Burmese CNER files to BIO/CoNLL format."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from functools import cache
from importlib import import_module
from pathlib import Path
from typing import Iterable, TextIO


TAG_DEFINITION_START = "# Tag definitions"
TAG_DEFINITION_END = "# Important distinction rules"
TAG_HEADING_RE = re.compile(r"^([A-Z][A-Z_]*):$")
TAG_ALIASES = {
    "0": "O",
    "ABIO": "ABIOD",
    "ABOID": "ABIOD",
    "NNUT": "NUT",
    "OCOUNT": "COUNT",
    "OPESTI": "PESTI",
    "PESYI": "PESTI",
    "QYT": "QTY",
}
MYANMAR_START = "\u1000"
MYANMAR_END = "\u109f"
MYANMAR_BASE_RANGES = (
    ("\u1000", "\u102a"),
    ("\u103f", "\u103f"),
    ("\u104e", "\u104f"),
    ("\u1050", "\u1055"),
    ("\u105a", "\u105d"),
    ("\u1061", "\u1061"),
    ("\u1065", "\u1066"),
    ("\u106e", "\u1070"),
    ("\u1075", "\u1081"),
    ("\u108e", "\u108e"),
)
MYANMAR_COMBINING = {
    "\u102b",
    "\u102c",
    "\u102d",
    "\u102e",
    "\u102f",
    "\u1030",
    "\u1031",
    "\u1032",
    "\u1036",
    "\u1037",
    "\u1038",
    "\u1039",
    "\u103a",
    "\u103b",
    "\u103c",
    "\u103d",
    "\u103e",
    "\u1056",
    "\u1057",
    "\u1058",
    "\u1059",
    "\u1062",
    "\u1063",
    "\u1064",
    "\u1067",
    "\u1068",
    "\u1069",
    "\u106a",
    "\u106b",
    "\u106c",
    "\u106d",
    "\u1071",
    "\u1072",
    "\u1073",
    "\u1074",
    "\u1082",
    "\u1083",
    "\u1084",
    "\u1085",
    "\u1086",
    "\u1087",
    "\u1088",
    "\u1089",
    "\u108a",
    "\u108b",
    "\u108c",
    "\u108d",
    "\u108f",
    "\u109a",
    "\u109b",
    "\u109c",
    "\u109d",
}


@dataclass(frozen=True)
class Segment:
    text: str
    tag: str


@dataclass
class Stats:
    files: int = 0
    lines: int = 0
    segments: int = 0
    output_rows: int = 0
    warnings: int = 0


def load_allowed_tags(instruction_path: Path | None) -> set[str]:
    """Load allowed tags from INSTRUCTION.MD, falling back to a bundled set."""
    fallback = {
        "O",
        "PER",
        "LOC",
        "ORG",
        "CROP",
        "VAR",
        "FOOD",
        "WEED",
        "PEST",
        "SEED",
        "DIS",
        "SYM",
        "CROP_PART",
        "BIOD",
        "ABIOD",
        "NUT",
        "DIST",
        "QTY",
        "TEMP",
        "TIME",
        "PERIOD",
        "PESTI",
        "FUNG",
        "HERB",
        "FERT",
        "PATH",
        "FARM_OP",
        "SOIL_TYPE",
        "METHOD",
        "EQUIP",
        "WEATHER",
        "SEASON",
        "HUM",
        "PRICE",
        "YIELD",
        "COUNT",
    }
    if instruction_path is None:
        return fallback
    if not instruction_path.exists():
        raise FileNotFoundError(f"Instruction file not found: {instruction_path}")

    tags = {"O"}
    in_definitions = False
    for raw_line in instruction_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == TAG_DEFINITION_START:
            in_definitions = True
            continue
        if line == TAG_DEFINITION_END:
            break
        if not in_definitions:
            continue
        match = TAG_HEADING_RE.match(line)
        if match:
            tags.add(match.group(1))

    return tags or fallback


def iter_input_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path not found: {input_path}")
    yield from sorted(input_path.rglob("*.txt"))


def warn(message: str, stats: Stats) -> None:
    stats.warnings += 1
    print(f"warning: {message}", file=sys.stderr)


def normalize_tag(tag: str) -> str:
    return TAG_ALIASES.get(tag, tag)


def recover_missing_at_segment(piece: str, allowed_tags: set[str]) -> Segment | None:
    for tag in sorted(allowed_tags - {"O"}, key=len, reverse=True):
        match = re.match(rf"^(.*?)[A-Za-z]*{re.escape(tag)}$", piece)
        if match and match.group(1).strip():
            return Segment(text=match.group(1).strip(), tag=tag)

    match = re.match(r"^(.*?)[A-Za-z]*O$", piece)
    if match and match.group(1).strip():
        return Segment(text=match.group(1).strip(), tag="O")

    return None


def in_range(char: str, start: str, end: str) -> bool:
    return ord(start) <= ord(char) <= ord(end)


def is_myanmar_char(char: str) -> bool:
    return in_range(char, MYANMAR_START, MYANMAR_END)


def is_myanmar_base(char: str) -> bool:
    return any(in_range(char, start, end) for start, end in MYANMAR_BASE_RANGES)


def is_myanmar_combining(char: str) -> bool:
    return char in MYANMAR_COMBINING


def syllable_units(text: str) -> list[str]:
    """Split Burmese text into lightweight syllable-like units.

    This is a deterministic heuristic, not a dictionary word segmenter. It keeps
    Myanmar combining marks with their base character and keeps stacked
    consonants joined through virama.
    """
    units: list[str] = []
    current = ""
    previous = ""

    def flush() -> None:
        nonlocal current
        if current:
            units.append(current)
            current = ""

    for char in text:
        if char.isspace():
            flush()
            previous = ""
            continue

        if not is_myanmar_char(char):
            if current and (current[-1].isalnum() and char.isalnum()):
                current += char
            else:
                flush()
                current = char
            previous = char
            continue

        if not current:
            current = char
        elif is_myanmar_combining(char) or previous == "\u1039":
            current += char
        elif is_myanmar_base(char):
            flush()
            current = char
        else:
            current += char
        previous = char

    flush()
    return units


@cache
def load_pyidaungsu():
    try:
        return import_module("pyidaungsu")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyidaungsu is required for this unit. Install it with: "
            "uv add pyidaungsu"
        ) from exc


def pyidaungsu_units(text: str, *, form: str | None = None) -> list[str]:
    pds = load_pyidaungsu()
    if form is None:
        tokens = pds.tokenize(text)
    else:
        tokens = pds.tokenize(text, form=form)
    return [token for token in tokens if token and not token.isspace()]


def parse_tagged_line(
    line: str,
    *,
    allowed_tags: set[str],
    source: str,
    line_no: int,
    stats: Stats,
    strict: bool,
) -> list[Segment]:
    segments: list[Segment] = []
    pieces = line.rstrip("\n").split("|")

    for index, piece in enumerate(pieces, start=1):
        if not piece:
            continue
        if "@" not in piece:
            message = f"{source}:{line_no}: segment {index} has no @TAG: {piece!r}"
            if strict:
                raise ValueError(message)
            warn(message, stats)
            recovered = recover_missing_at_segment(piece.strip(), allowed_tags)
            if recovered:
                segments.append(recovered)
            elif piece.strip():
                segments.append(Segment(text=piece.strip(), tag="O"))
            continue

        text, tag = piece.rsplit("@", 1)
        text = text.strip()
        original_tag = tag.strip()
        tag = normalize_tag(original_tag)
        if not text:
            warn(f"{source}:{line_no}: segment {index} has empty text; skipped", stats)
            continue
        if tag != original_tag:
            warn(
                f"{source}:{line_no}: normalized tag {original_tag!r} to {tag!r}",
                stats,
            )
        if tag not in allowed_tags:
            message = f"{source}:{line_no}: unknown tag {tag!r} in segment {piece!r}"
            if strict:
                raise ValueError(message)
            warn(message, stats)
            continue

        segments.append(Segment(text=text, tag=tag))

    return segments


def units_for(text: str, unit: str) -> list[str]:
    if unit == "segment":
        return [text]
    if unit == "char":
        return list(text)
    if unit == "syllable":
        return syllable_units(text)
    if unit == "pyidaungsu-syllable":
        return pyidaungsu_units(text)
    if unit == "pyidaungsu-word":
        return pyidaungsu_units(text, form="word")
    if unit == "space":
        return text.split()
    raise ValueError(f"Unsupported unit: {unit}")


def bio_rows(segments: list[Segment], *, unit: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for segment in segments:
        parts = units_for(segment.text, unit)
        if segment.tag == "O":
            rows.extend((part, "O") for part in parts)
            continue
        for index, part in enumerate(parts):
            prefix = "B" if index == 0 else "I"
            rows.append((part, f"{prefix}-{segment.tag}"))
    return rows


def write_rows(
    rows: list[tuple[str, str]],
    output: TextIO,
    *,
    labels_only: bool,
    separator: str,
) -> int:
    for token, label in rows:
        if labels_only:
            output.write(f"{label}\n")
        else:
            output.write(f"{token}{separator}{label}\n")
    output.write("\n")
    return len(rows)


def convert_file(
    path: Path,
    output: TextIO,
    *,
    allowed_tags: set[str],
    unit: str,
    labels_only: bool,
    separator: str,
    strict: bool,
    stats: Stats,
) -> None:
    stats.files += 1
    with path.open("r", encoding="utf-8") as input_file:
        for line_no, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            segments = parse_tagged_line(
                line,
                allowed_tags=allowed_tags,
                source=str(path),
                line_no=line_no,
                stats=stats,
                strict=strict,
            )
            if not segments:
                continue

            rows = bio_rows(segments, unit=unit)
            stats.lines += 1
            stats.segments += len(segments)
            stats.output_rows += write_rows(
                rows,
                output,
                labels_only=labels_only,
                separator=separator,
            )


def print_tag_table(tags: set[str]) -> None:
    for tag in sorted(tags):
        if tag == "O":
            print("O")
        else:
            print(f"B-{tag}")
            print(f"I-{tag}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Burmese `token@TAG|` files to BIO/CoNLL format.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="Tagged .txt file or directory of .txt files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output BIO file. Defaults to stdout.",
    )
    parser.add_argument(
        "--instruction",
        type=Path,
        default=Path("INSTRUCTION.MD"),
        help="Instruction file used to load allowed tags.",
    )
    parser.add_argument(
        "--unit",
        choices=(
            "segment",
            "pyidaungsu-word",
            "pyidaungsu-syllable",
            "syllable",
            "char",
            "space",
        ),
        default="segment",
        help=(
            "BIO unit. Use pyidaungsu-word for Burmese word tokenization, "
            "pyidaungsu-syllable for pyidaungsu syllable tokenization, or "
            "syllable for the no-dependency heuristic fallback."
        ),
    )
    parser.add_argument(
        "--labels-only",
        action="store_true",
        help="Write only BIO labels, one per line.",
    )
    parser.add_argument(
        "--separator",
        default="\t",
        help="Token/label separator for CoNLL output. Default: tab.",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Warn and skip malformed/unknown-tag segments instead of failing.",
    )
    parser.add_argument(
        "--print-tags",
        action="store_true",
        help="Print the BIO tag table loaded from INSTRUCTION.MD and exit.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    allowed_tags = load_allowed_tags(args.instruction)
    if args.print_tags:
        print_tag_table(allowed_tags)
        return 0

    if args.input is None:
        parser.error("input is required unless --print-tags is used")

    stats = Stats()
    strict = not args.no_strict

    output_handle: TextIO
    should_close = False
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output_handle = args.output.open("w", encoding="utf-8")
        should_close = True
    else:
        output_handle = sys.stdout

    try:
        for path in iter_input_files(args.input):
            convert_file(
                path,
                output_handle,
                allowed_tags=allowed_tags,
                unit=args.unit,
                labels_only=args.labels_only,
                separator=args.separator,
                strict=strict,
                stats=stats,
            )
    finally:
        if should_close:
            output_handle.close()

    print(
        "converted "
        f"{stats.files} file(s), {stats.lines} sentence(s), "
        f"{stats.segments} segment(s), {stats.output_rows} BIO row(s), "
        f"{stats.warnings} warning(s)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
