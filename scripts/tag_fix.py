#!/usr/bin/env python3
"""Retag exact terms across `text@TAG|` Burmese CNER files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

try:
    from tagged_to_bio import iter_input_files, load_allowed_tags, normalize_tag
except ModuleNotFoundError:  # Allow `from scripts.tag_fix import ...` from repo root.
    from scripts.tagged_to_bio import iter_input_files, load_allowed_tags, normalize_tag


@dataclass(frozen=True)
class Segment:
    text: str
    tag: str


@dataclass
class RetagStats:
    files: int = 0
    changed_files: int = 0
    lines: int = 0
    changed_lines: int = 0
    occurrences: int = 0
    changed_occurrences: int = 0
    already_correct: int = 0


def parse_line(line: str) -> list[Segment]:
    """Parse a tagged line while tolerating no-tag pieces as O segments."""
    text = line.rstrip("\n")
    if not text:
        return []

    segments: list[Segment] = []
    pieces = text.split("|")
    for index, piece in enumerate(pieces):
        if not piece and index == len(pieces) - 1 and text.endswith("|"):
            continue
        if not piece:
            continue
        if "@" not in piece:
            segments.append(Segment(text=piece, tag="O"))
            continue

        segment_text, raw_tag = piece.rsplit("@", 1)
        tag = normalize_tag(raw_tag.strip()) or "O"
        segments.append(Segment(text=segment_text, tag=tag))
    return segments


def format_line(segments: list[Segment]) -> str:
    return "".join(f"{segment.text}@{segment.tag}|" for segment in segments)


def merge_consecutive_o(segments: list[Segment]) -> list[Segment]:
    merged: list[Segment] = []
    for segment in segments:
        if not segment.text:
            continue
        if merged and merged[-1].tag == "O" and segment.tag == "O":
            merged[-1] = Segment(text=merged[-1].text + segment.text, tag="O")
            continue
        merged.append(segment)
    return merged


def flatten_segments(segments: list[Segment]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    tags_by_char: list[str] = []
    for segment in segments:
        text_parts.append(segment.text)
        tags_by_char.extend([segment.tag] * len(segment.text))
    return "".join(text_parts), tags_by_char


def append_tagged_span(output: list[Segment], text: str, tag: str) -> None:
    if not text:
        return
    if output and output[-1].tag == tag:
        output[-1] = Segment(text=output[-1].text + text, tag=tag)
        return
    output.append(Segment(text=text, tag=tag))


def append_original_span(output: list[Segment], plain_text: str, tags_by_char: list[str], start: int, end: int) -> None:
    cursor = start
    while cursor < end:
        tag = tags_by_char[cursor]
        next_cursor = cursor + 1
        while next_cursor < end and tags_by_char[next_cursor] == tag:
            next_cursor += 1
        append_tagged_span(output, plain_text[cursor:next_cursor], tag)
        cursor = next_cursor


def retag_line(line: str, *, term: str, target_tag: str, stats: RetagStats) -> str:
    original = line.rstrip("\n")

    segments = parse_line(line)
    if not segments:
        return original

    plain_text, tags_by_char = flatten_segments(segments)
    if term not in plain_text:
        return original

    retagged: list[Segment] = []
    cursor = 0
    term_len = len(term)
    line_changed = False
    while True:
        index = plain_text.find(term, cursor)
        if index == -1:
            break

        append_original_span(retagged, plain_text, tags_by_char, cursor, index)
        append_tagged_span(retagged, term, target_tag)

        stats.occurrences += 1
        original_tags = set(tags_by_char[index : index + term_len])
        if original_tags == {target_tag}:
            stats.already_correct += 1
        else:
            line_changed = True
            stats.changed_occurrences += 1

        cursor = index + term_len

    if not line_changed:
        return original

    append_original_span(retagged, plain_text, tags_by_char, cursor, len(plain_text))

    return format_line(merge_consecutive_o(retagged))


def output_path_for(input_file: Path, *, input_root: Path, output_dir: Path) -> Path:
    if input_root.is_file():
        return output_dir / input_file.name
    return output_dir / input_file.relative_to(input_root)


def retag_file(
    path: Path,
    *,
    input_root: Path,
    output_dir: Path | None,
    in_place: bool,
    dry_run: bool,
    term: str,
    target_tag: str,
    stats: RetagStats,
) -> None:
    stats.files += 1
    original_text = path.read_text(encoding="utf-8")
    had_trailing_newline = original_text.endswith("\n")
    original_lines = original_text.splitlines()

    fixed_lines: list[str] = []
    file_changed = False
    for line in original_lines:
        stats.lines += 1
        fixed = retag_line(line, term=term, target_tag=target_tag, stats=stats)
        fixed_lines.append(fixed)
        if fixed != line:
            file_changed = True
            stats.changed_lines += 1

    if not file_changed:
        return

    stats.changed_files += 1
    fixed_text = "\n".join(fixed_lines)
    if had_trailing_newline:
        fixed_text += "\n"

    if dry_run:
        return

    if in_place:
        path.write_text(fixed_text, encoding="utf-8")
        return

    if output_dir is None:
        raise ValueError("output_dir is required unless in_place is true")
    target = output_path_for(path, input_root=input_root, output_dir=output_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(fixed_text, encoding="utf-8")


def retag_path(
    input_path: Path,
    *,
    term: str,
    target_tag: str,
    output_dir: Path | None,
    in_place: bool,
    dry_run: bool,
) -> RetagStats:
    stats = RetagStats()
    for path in iter_input_files(input_path):
        retag_file(
            path,
            input_root=input_path,
            output_dir=output_dir,
            in_place=in_place,
            dry_run=dry_run,
            term=term,
            target_tag=target_tag,
            stats=stats,
        )
    return stats


def print_summary(stats: RetagStats, *, destination: str) -> None:
    print(f"destination: {destination}")
    print(f"files: {stats.files}")
    print(f"changed_files: {stats.changed_files}")
    print(f"lines: {stats.lines}")
    print(f"changed_lines: {stats.changed_lines}")
    print(f"matched_occurrences: {stats.occurrences}")
    print(f"changed_occurrences: {stats.changed_occurrences}")
    if stats.already_correct:
        print(f"already_correct_occurrences: {stats.already_correct}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retag every exact term occurrence in Burmese `text@TAG|` .txt files.",
    )
    parser.add_argument("input", type=Path, help="Tagged .txt file or directory of .txt files.")
    parser.add_argument("term", help="Exact text to retag, e.g. အစိုဓာတ်")
    parser.add_argument("tag", help="Target tag, e.g. WEATHER")
    parser.add_argument(
        "--instruction",
        type=Path,
        default=Path("INSTRUCTION.MD"),
        help="Instruction file used to load allowed tags. Default: INSTRUCTION.MD",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Write changed files under this directory instead of editing in place.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show how many files/lines would change without writing files.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    term = args.term
    if not term:
        parser.error("term must not be empty")

    allowed_tags = load_allowed_tags(args.instruction)
    target_tag = normalize_tag(args.tag.strip())
    if target_tag not in allowed_tags:
        allowed = ", ".join(sorted(allowed_tags))
        parser.error(f"unknown tag {args.tag!r}; allowed tags: {allowed}")

    in_place = args.output_dir is None
    stats = retag_path(
        args.input,
        term=term,
        target_tag=target_tag,
        output_dir=args.output_dir,
        in_place=in_place,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        destination = "dry-run"
    elif in_place:
        destination = "in-place"
    else:
        destination = str(args.output_dir)
    print_summary(stats, destination=destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
