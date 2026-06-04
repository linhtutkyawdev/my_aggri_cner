#!/usr/bin/env python3
"""Automatically fix mechanical issues in `text@TAG|` tagged files."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from tagged_to_bio import iter_input_files, load_allowed_tags, normalize_tag

MYANMAR_START = "\u1000"
MYANMAR_END = "\u109f"
LATIN_REPLACEMENTS = {
    "F1": "အက်ဖ်ဝမ်း",
    "f1": "အက်ဖ်ဝမ်း",
}


@dataclass
class Segment:
    text: str
    tag: str


@dataclass
class FixStats:
    files: int = 0
    lines_read: int = 0
    lines_written: int = 0
    changed_lines: int = 0
    fixes: Counter[str] = field(default_factory=Counter)


def likely_missing_at(piece: str, allowed_tags: set[str]) -> str | None:
    stripped = piece.strip()
    for tag in sorted(allowed_tags, key=len, reverse=True):
        if stripped.endswith(tag) and stripped[: -len(tag)].strip():
            return tag
    return None


def is_myanmar_char(char: str) -> bool:
    return bool(char) and ord(MYANMAR_START) <= ord(char) <= ord(MYANMAR_END)


def remove_stray_latin_letters(text: str, stats: FixStats) -> str:
    chars: list[str] = []
    changed = False
    for index, char in enumerate(text):
        if not char.isascii() or not char.isalpha():
            chars.append(char)
            continue

        previous_char = text[index - 1] if index > 0 else ""
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if is_myanmar_char(previous_char) or is_myanmar_char(next_char):
            changed = True
            continue

        chars.append(char)

    if changed:
        stats.fixes["remove_stray_latin_letter"] += 1
    return "".join(chars)


def normalize_latin_units(text: str, stats: FixStats) -> str:
    normalized = text.replace("°C", "ဒီဂရီစင်တီဂရိတ်")
    normalized = normalized.replace("℃", "ဒီဂရီစင်တီဂရိတ်")
    if normalized != text:
        stats.fixes["normalize_temperature_unit"] += 1
    return normalized


def replace_known_latin_terms(text: str, stats: FixStats) -> str:
    normalized = text
    for source, replacement in LATIN_REPLACEMENTS.items():
        normalized = normalized.replace(source, replacement)
    if normalized != text:
        stats.fixes["replace_known_latin_term"] += 1
    return normalized


def clean_segment_text(text: str, stats: FixStats) -> str:
    compact_text = "".join(text.split())
    if compact_text != text:
        stats.fixes["remove_spaces_in_text"] += 1
        text = compact_text

    if "@" in text:
        text = text.replace("@", "")
        stats.fixes["remove_stray_at_in_text"] += 1

    text = normalize_latin_units(text, stats)
    text = replace_known_latin_terms(text, stats)
    text = remove_stray_latin_letters(text, stats)
    return text


def insert_missing_at_for_embedded_tag_names(line: str, allowed_tags: set[str], stats: FixStats) -> str:
    """Repair leaked tag names like `၁၀အိတ်COUNT|` or `၃နှစ်qPERIOD|`."""
    tags = sorted(allowed_tags - {"O"}, key=len, reverse=True)
    index = 0
    output: list[str] = []
    changed = False

    while index < len(line):
        matched = False
        for tag in tags:
            if not line.startswith(tag, index):
                continue

            previous_char = line[index - 1] if index > 0 else ""
            next_char = line[index + len(tag) : index + len(tag) + 1]
            previous_is_latin = previous_char.isascii() and previous_char.isalpha()
            next_is_latin = next_char.isascii() and next_char.isalpha()
            if previous_char == "@" or previous_is_latin or next_is_latin:
                continue

            output.append(f"@{tag}")
            changed = True
            index += len(tag)
            matched = True
            break
        if not matched:
            output.append(line[index])
            index += 1

    if changed:
        stats.fixes["insert_missing_at_before_embedded_tag"] += 1
    return "".join(output)


def split_embedded_tag_markers(line: str, allowed_tags: set[str], stats: FixStats) -> str:
    """Insert a missing pipe after known @TAG markers inside a segment."""
    tags = sorted(allowed_tags - {"O"}, key=len, reverse=True)
    index = 0
    output: list[str] = []
    changed = False

    while index < len(line):
        matched = False
        for tag in tags:
            marker = f"@{tag}"
            if not line.startswith(marker, index):
                continue

            after = index + len(marker)
            next_char = line[after : after + 1]
            remaining = line[after:]
            should_close = next_char not in ("", "|") and "@" in remaining
            output.append(marker)
            if should_close:
                output.append("|")
                changed = True
            index = after
            matched = True
            break
        if not matched:
            output.append(line[index])
            index += 1

    if changed:
        stats.fixes["split_embedded_tag_marker"] += 1
    return "".join(output)


def parse_piece(piece: str, *, allowed_tags: set[str], stats: FixStats) -> Segment | None:
    piece = piece.strip()
    if not piece:
        stats.fixes["remove_empty_pipe_segment"] += 1
        return None

    if "@" not in piece:
        missing_tag = likely_missing_at(piece, allowed_tags)
        if missing_tag:
            text = piece[: -len(missing_tag)].strip()
            text = clean_segment_text(text, stats)
            stats.fixes["insert_missing_at_before_tag"] += 1
            return Segment(text=text, tag=missing_tag) if text else None

        stats.fixes["tag_no_tag_segment_as_o"] += 1
        return Segment(text=piece, tag="O")

    text, raw_tag = piece.rsplit("@", 1)
    text = text.strip()
    original_tag = raw_tag.strip()
    tag = normalize_tag(original_tag)

    if not text:
        stats.fixes["remove_no_text_segment"] += 1
        return None

    if not original_tag:
        stats.fixes["empty_tag_to_o"] += 1
        tag = "O"
    elif tag != original_tag:
        stats.fixes["normalize_tag_alias"] += 1

    if tag not in allowed_tags:
        stats.fixes["unknown_tag_to_o"] += 1
        tag = "O"

    text = clean_segment_text(text, stats)
    return Segment(text=text, tag=tag)


def merge_consecutive_o(segments: list[Segment], stats: FixStats) -> list[Segment]:
    merged: list[Segment] = []
    for segment in segments:
        if merged and merged[-1].tag == "O" and segment.tag == "O":
            merged[-1].text += segment.text
            stats.fixes["merge_consecutive_o_segments"] += 1
        else:
            merged.append(segment)
    return merged


def format_line(segments: list[Segment]) -> str:
    return "".join(f"{segment.text}@{segment.tag}|" for segment in segments)


def fix_line(
    raw_line: str,
    *,
    allowed_tags: set[str],
    stats: FixStats,
    drop_o_only: bool,
) -> str | None:
    line = raw_line.strip()
    if not line:
        stats.fixes["drop_empty_line"] += 1
        return None

    if line != raw_line.rstrip("\n"):
        stats.fixes["trim_outer_whitespace"] += 1

    line = insert_missing_at_for_embedded_tag_names(line, allowed_tags, stats)
    line = split_embedded_tag_markers(line, allowed_tags, stats)

    if not line.endswith("|"):
        line += "|"
        stats.fixes["add_missing_final_pipe"] += 1

    segments: list[Segment] = []
    pieces = line.split("|")
    for index, piece in enumerate(pieces, start=1):
        if not piece and index == len(pieces) and line.endswith("|"):
            continue
        segment = parse_piece(piece, allowed_tags=allowed_tags, stats=stats)
        if segment is not None:
            segments.append(segment)
    segments = merge_consecutive_o(segments, stats)

    if not segments:
        stats.fixes["drop_line_with_no_segments"] += 1
        return None

    if drop_o_only and all(segment.tag == "O" for segment in segments):
        stats.fixes["drop_o_only_line"] += 1
        return None

    return format_line(segments)


def output_path_for(input_file: Path, *, input_root: Path, output_dir: Path) -> Path:
    if input_root.is_file():
        return output_dir / input_file.name
    return output_dir / input_file.relative_to(input_root)


def fix_file(
    path: Path,
    *,
    allowed_tags: set[str],
    input_root: Path,
    output_dir: Path | None,
    in_place: bool,
    drop_duplicates: bool,
    drop_o_only: bool,
    seen_lines: set[str],
    stats: FixStats,
) -> None:
    stats.files += 1
    original_lines = path.read_text(encoding="utf-8").splitlines()
    fixed_lines: list[str] = []

    for raw_line in original_lines:
        stats.lines_read += 1
        fixed = fix_line(
            raw_line,
            allowed_tags=allowed_tags,
            stats=stats,
            drop_o_only=drop_o_only,
        )
        if fixed is None:
            continue

        if drop_duplicates and fixed in seen_lines:
            stats.fixes["drop_duplicate_line"] += 1
            continue
        seen_lines.add(fixed)
        fixed_lines.append(fixed)

        if fixed != raw_line.rstrip("\n"):
            stats.changed_lines += 1

    stats.lines_written += len(fixed_lines)
    output_text = "\n".join(fixed_lines)
    if output_text:
        output_text += "\n"

    if in_place:
        path.write_text(output_text, encoding="utf-8")
        return

    if output_dir is None:
        raise ValueError("output_dir is required unless in_place is true")
    target = output_path_for(path, input_root=input_root, output_dir=output_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output_text, encoding="utf-8")


def fix_path(
    input_path: Path,
    *,
    allowed_tags: set[str],
    output_dir: Path | None,
    in_place: bool,
    drop_duplicates: bool,
    drop_o_only: bool,
) -> FixStats:
    stats = FixStats()
    seen_lines: set[str] = set()
    for path in iter_input_files(input_path):
        fix_file(
            path,
            allowed_tags=allowed_tags,
            input_root=input_path,
            output_dir=output_dir,
            in_place=in_place,
            drop_duplicates=drop_duplicates,
            drop_o_only=drop_o_only,
            seen_lines=seen_lines,
            stats=stats,
        )
    return stats


def print_summary(stats: FixStats, *, destination: str) -> None:
    print(f"destination: {destination}")
    print(f"files: {stats.files}")
    print(f"lines_read: {stats.lines_read}")
    print(f"lines_written: {stats.lines_written}")
    print(f"changed_lines: {stats.changed_lines}")
    if not stats.fixes:
        print("fixes: none")
        return

    print()
    print("FIX                            COUNT")
    print("-----------------------------  -----")
    for code, count in sorted(stats.fixes.items(), key=lambda item: (-item[1], item[0])):
        print(f"{code:<29}  {count:>5}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automatically fix mechanical issues in Burmese `text@TAG|` tagged .txt files.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("corrected_tagged"),
        help="Tagged .txt file or directory of .txt files. Default: corrected_tagged",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("fixed_tagged"),
        help="Directory for fixed files when not using --in-place. Default: fixed_tagged",
    )
    parser.add_argument(
        "--instruction",
        type=Path,
        default=Path("INSTRUCTION.MD"),
        help="Instruction file used to load allowed tags. Default: INSTRUCTION.MD",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite input files instead of writing to --output-dir.",
    )
    parser.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="Keep duplicate fixed lines. Default drops duplicates across all scanned files.",
    )
    parser.add_argument(
        "--keep-o-only",
        action="store_true",
        help="Keep lines that contain only O tags. Default drops them.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    allowed_tags = load_allowed_tags(args.instruction)
    stats = fix_path(
        args.input,
        allowed_tags=allowed_tags,
        output_dir=None if args.in_place else args.output_dir,
        in_place=args.in_place,
        drop_duplicates=not args.keep_duplicates,
        drop_o_only=not args.keep_o_only,
    )
    destination = "in-place" if args.in_place else str(args.output_dir)
    print_summary(stats, destination=destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
