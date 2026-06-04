#!/usr/bin/env python3
"""Count `token@TAG|` segment tags in Burmese CNER tagged files."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from tagged_to_bio import iter_input_files, load_allowed_tags, normalize_tag


@dataclass
class FileStats:
    lines: int = 0
    tagged_lines: int = 0
    segments: int = 0
    malformed_segments: int = 0
    unknown_tags: Counter[str] = field(default_factory=Counter)
    tags: Counter[str] = field(default_factory=Counter)


@dataclass
class CountStats:
    files: int = 0
    lines: int = 0
    tagged_lines: int = 0
    segments: int = 0
    malformed_segments: int = 0
    unknown_tags: Counter[str] = field(default_factory=Counter)
    tags: Counter[str] = field(default_factory=Counter)
    per_file: dict[str, FileStats] = field(default_factory=dict)


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def count_line(
    line: str,
    *,
    allowed_tags: set[str],
    source: str,
    line_no: int,
    strict: bool,
    file_stats: FileStats,
) -> None:
    has_known_entity = False

    for index, piece in enumerate(line.rstrip("\n").split("|"), start=1):
        if not piece:
            continue
        if "@" not in piece:
            message = f"{source}:{line_no}: segment {index} has no @TAG: {piece!r}"
            if strict:
                raise ValueError(message)
            warn(message)
            file_stats.malformed_segments += 1
            continue

        text, raw_tag = piece.rsplit("@", 1)
        text = text.strip()
        original_tag = raw_tag.strip()
        tag = normalize_tag(original_tag)

        if not text:
            message = f"{source}:{line_no}: segment {index} has empty text"
            if strict:
                raise ValueError(message)
            warn(message)
            file_stats.malformed_segments += 1
            continue

        if tag not in allowed_tags:
            message = f"{source}:{line_no}: unknown tag {tag!r} in segment {piece!r}"
            if strict:
                raise ValueError(message)
            warn(message)
            file_stats.unknown_tags[tag] += 1
            continue

        file_stats.tags[tag] += 1
        file_stats.segments += 1
        if tag != "O":
            has_known_entity = True

    if has_known_entity:
        file_stats.tagged_lines += 1


def merge_file_stats(total: CountStats, path: Path, file_stats: FileStats) -> None:
    total.files += 1
    total.lines += file_stats.lines
    total.tagged_lines += file_stats.tagged_lines
    total.segments += file_stats.segments
    total.malformed_segments += file_stats.malformed_segments
    total.tags.update(file_stats.tags)
    total.unknown_tags.update(file_stats.unknown_tags)
    total.per_file[str(path)] = file_stats


def count_path(input_path: Path, *, allowed_tags: set[str], strict: bool) -> CountStats:
    total = CountStats()
    for path in iter_input_files(input_path):
        file_stats = FileStats()
        with path.open("r", encoding="utf-8") as tagged_file:
            for line_no, line in enumerate(tagged_file, start=1):
                if not line.strip():
                    continue
                file_stats.lines += 1
                count_line(
                    line,
                    allowed_tags=allowed_tags,
                    source=str(path),
                    line_no=line_no,
                    strict=strict,
                    file_stats=file_stats,
                )
        merge_file_stats(total, path, file_stats)
    return total


def printable_tags(counter: Counter[str], *, include_o: bool) -> list[tuple[str, int]]:
    rows = counter.items() if include_o else ((tag, count) for tag, count in counter.items() if tag != "O")
    return sorted(rows, key=lambda item: (-item[1], item[0]))


def print_table(stats: CountStats, *, include_o: bool) -> None:
    rows = printable_tags(stats.tags, include_o=include_o)
    denominator = sum(count for _, count in rows) or 1
    tag_width = max([len("TAG"), *(len(tag) for tag, _ in rows)], default=len("TAG"))
    count_width = max([len("COUNT"), *(len(str(count)) for _, count in rows)], default=len("COUNT"))

    print(f"{'TAG':<{tag_width}}  {'COUNT':>{count_width}}  PERCENT")
    print(f"{'-' * tag_width}  {'-' * count_width}  -------")
    for tag, count in rows:
        percent = count / denominator * 100
        print(f"{tag:<{tag_width}}  {count:>{count_width}}  {percent:6.2f}%")

    print()
    print(f"files: {stats.files}")
    print(f"lines: {stats.lines}")
    print(f"lines_with_entity: {stats.tagged_lines}")
    print(f"counted_segments: {stats.segments}")
    if stats.malformed_segments:
        print(f"malformed_segments: {stats.malformed_segments}")
    if stats.unknown_tags:
        unknown = ", ".join(f"{tag}={count}" for tag, count in sorted(stats.unknown_tags.items()))
        print(f"unknown_tags: {unknown}")


def print_per_file(stats: CountStats, *, include_o: bool) -> None:
    for path, file_stats in stats.per_file.items():
        print()
        print(path)
        for tag, count in printable_tags(file_stats.tags, include_o=include_o):
            print(f"  {tag}: {count}")


def stats_to_json(stats: CountStats, *, include_o: bool) -> str:
    tags = dict(printable_tags(stats.tags, include_o=include_o))
    per_file = {
        path: {
            "lines": file_stats.lines,
            "lines_with_entity": file_stats.tagged_lines,
            "counted_segments": file_stats.segments,
            "malformed_segments": file_stats.malformed_segments,
            "unknown_tags": dict(file_stats.unknown_tags),
            "tags": dict(printable_tags(file_stats.tags, include_o=include_o)),
        }
        for path, file_stats in stats.per_file.items()
    }
    payload = {
        "files": stats.files,
        "lines": stats.lines,
        "lines_with_entity": stats.tagged_lines,
        "counted_segments": stats.segments,
        "malformed_segments": stats.malformed_segments,
        "unknown_tags": dict(stats.unknown_tags),
        "tags": tags,
        "per_file": per_file,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Count tags in Burmese `token@TAG|` tagged .txt files.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("corrected_tagged"),
        help="Tagged .txt file or directory of .txt files. Default: corrected_tagged",
    )
    parser.add_argument(
        "--instruction",
        type=Path,
        default=Path("INSTRUCTION.MD"),
        help="Instruction file used to load allowed tags. Default: INSTRUCTION.MD",
    )
    parser.add_argument(
        "--include-o",
        action="store_true",
        help="Include O segments in the printed tag table. Default counts entity tags only.",
    )
    parser.add_argument(
        "--per-file",
        action="store_true",
        help="Print a tag breakdown for each input file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print counts as JSON.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on the first malformed/unknown-tag segment. Default warns and skips it.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    allowed_tags = load_allowed_tags(args.instruction)
    stats = count_path(args.input, allowed_tags=allowed_tags, strict=args.strict)

    if args.json:
        print(stats_to_json(stats, include_o=args.include_o))
    else:
        print_table(stats, include_o=args.include_o)
        if args.per_file:
            print_per_file(stats, include_o=args.include_o)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
