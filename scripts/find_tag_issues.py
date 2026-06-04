#!/usr/bin/env python3
"""Find cleanup issues in `text@TAG|` Burmese CNER tagged files."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from tagged_to_bio import iter_input_files, load_allowed_tags, normalize_tag


TAG_IN_TEXT_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")
LATIN_RE = re.compile(r"[A-Za-z]")
SPACE_RE = re.compile(r"\s")
PUNCT_ONLY_RE = re.compile(r"^[\W_]+$", re.UNICODE)

ISSUE_PRIORITY = {
    "no_text_segment": 10,
    "no_tag_segment": 20,
    "missing_at_before_tag": 30,
    "missing_final_pipe": 40,
    "embedded_tag_marker": 50,
    "non_closing_tag_indicator": 60,
    "empty_tag": 70,
    "unknown_tag": 80,
    "empty_pipe_segment": 90,
    "tag_alias": 100,
    "line_has_no_valid_segments": 110,
    "line_has_only_o_tags": 120,
    "duplicate_line": 130,
    "latin_text": 140,
    "space_in_segment_text": 150,
    "outer_whitespace": 160,
    "empty_line": 170,
    "punctuation_tagged_as_entity": 180,
    "consecutive_o_segments": 190,
}


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    line: int
    segment: int | None
    detail: str
    text: str


@dataclass
class ScanStats:
    files: int = 0
    lines: int = 0
    segments: int = 0
    issues: list[Issue] | None = None
    issue_counts: Counter[str] | None = None

    def __post_init__(self) -> None:
        if self.issues is None:
            self.issues = []
        if self.issue_counts is None:
            self.issue_counts = Counter()


def add_issue(
    stats: ScanStats,
    *,
    code: str,
    path: Path,
    line_no: int,
    segment_no: int | None,
    detail: str,
    text: str,
) -> None:
    stats.issue_counts[code] += 1
    stats.issues.append(
        Issue(
            code=code,
            path=str(path),
            line=line_no,
            segment=segment_no,
            detail=detail,
            text=text.strip(),
        )
    )


def likely_missing_at(piece: str, allowed_tags: set[str]) -> str | None:
    stripped = piece.strip()
    for tag in sorted(allowed_tags, key=len, reverse=True):
        if stripped.endswith(tag) and stripped[: -len(tag)].strip():
            return tag
    return None


def visible(text: str, limit: int = 120) -> str:
    text = text.replace("\t", "\\t")
    return text if len(text) <= limit else f"{text[:limit]}..."


def scan_segment(
    piece: str,
    *,
    allowed_tags: set[str],
    path: Path,
    line_no: int,
    segment_no: int,
    stats: ScanStats,
) -> tuple[str | None, bool]:
    """Scan one pipe-delimited segment.

    Returns the normalized tag when a valid-looking tag exists, plus whether the
    segment was counted as structurally valid.
    """
    if not piece:
        add_issue(
            stats,
            code="empty_pipe_segment",
            path=path,
            line_no=line_no,
            segment_no=segment_no,
            detail="empty segment between pipes; often caused by a doubled pipe",
            text=piece,
        )
        return None, False

    if "@" not in piece:
        missing_tag = likely_missing_at(piece, allowed_tags)
        if missing_tag:
            add_issue(
                stats,
                code="missing_at_before_tag",
                path=path,
                line_no=line_no,
                segment_no=segment_no,
                detail=f"looks like tag {missing_tag!r} is attached without @",
                text=piece,
            )
        else:
            add_issue(
                stats,
                code="no_tag_segment",
                path=path,
                line_no=line_no,
                segment_no=segment_no,
                detail="segment has text but no @TAG marker",
                text=piece,
            )
        return None, False

    text, raw_tag = piece.rsplit("@", 1)
    text = text.strip()
    original_tag = raw_tag.strip()
    tag = normalize_tag(original_tag)

    if not text:
        add_issue(
            stats,
            code="no_text_segment",
            path=path,
            line_no=line_no,
            segment_no=segment_no,
            detail=f"tag {original_tag!r} has no text before @",
            text=piece,
        )
        return tag or None, False

    if "@" in text:
        add_issue(
            stats,
            code="embedded_tag_marker",
            path=path,
            line_no=line_no,
            segment_no=segment_no,
            detail="text contains another @ marker; often a missing pipe after a tag",
            text=piece,
        )

    embedded_tags = [match.group(1) for match in TAG_IN_TEXT_RE.finditer(text)]
    for embedded_tag in embedded_tags:
        if embedded_tag in allowed_tags:
            add_issue(
                stats,
                code="non_closing_tag_indicator",
                path=path,
                line_no=line_no,
                segment_no=segment_no,
                detail=f"found @{embedded_tag} inside segment text before final tag",
                text=piece,
            )

    if not original_tag:
        add_issue(
            stats,
            code="empty_tag",
            path=path,
            line_no=line_no,
            segment_no=segment_no,
            detail="segment has @ but no tag after it",
            text=piece,
        )
        return None, False

    if tag != original_tag:
        add_issue(
            stats,
            code="tag_alias",
            path=path,
            line_no=line_no,
            segment_no=segment_no,
            detail=f"tag {original_tag!r} normalizes to {tag!r}",
            text=piece,
        )

    if tag not in allowed_tags:
        add_issue(
            stats,
            code="unknown_tag",
            path=path,
            line_no=line_no,
            segment_no=segment_no,
            detail=f"tag {tag!r} is not in INSTRUCTION.MD",
            text=piece,
        )
        return tag, False

    if SPACE_RE.search(text):
        add_issue(
            stats,
            code="space_in_segment_text",
            path=path,
            line_no=line_no,
            segment_no=segment_no,
            detail="instruction says final output should remove spaces",
            text=piece,
        )

    text_without_tag_markers = TAG_IN_TEXT_RE.sub("", text)
    if LATIN_RE.search(text_without_tag_markers):
        add_issue(
            stats,
            code="latin_text",
            path=path,
            line_no=line_no,
            segment_no=segment_no,
            detail="instruction says English/Latin text should usually be removed or transliterated",
            text=piece,
        )

    if tag != "O" and PUNCT_ONLY_RE.match(text):
        add_issue(
            stats,
            code="punctuation_tagged_as_entity",
            path=path,
            line_no=line_no,
            segment_no=segment_no,
            detail="punctuation should usually be tagged as O",
            text=piece,
        )

    stats.segments += 1
    return tag, True


def scan_line(
    line: str,
    *,
    allowed_tags: set[str],
    path: Path,
    line_no: int,
    stats: ScanStats,
) -> str:
    raw_line = line.rstrip("\n")
    stripped = raw_line.strip()

    if not stripped:
        add_issue(
            stats,
            code="empty_line",
            path=path,
            line_no=line_no,
            segment_no=None,
            detail="empty line should be removed",
            text=raw_line,
        )
        return stripped

    if raw_line != stripped:
        add_issue(
            stats,
            code="outer_whitespace",
            path=path,
            line_no=line_no,
            segment_no=None,
            detail="line has leading or trailing whitespace",
            text=raw_line,
        )

    if not stripped.endswith("|"):
        add_issue(
            stats,
            code="missing_final_pipe",
            path=path,
            line_no=line_no,
            segment_no=None,
            detail="line does not end with closing |",
            text=raw_line,
        )

    tags: list[str] = []
    previous_tag: str | None = None
    pieces = stripped.split("|")
    for segment_no, piece in enumerate(pieces, start=1):
        if not piece and segment_no == len(pieces) and stripped.endswith("|"):
            continue
        tag, structurally_valid = scan_segment(
            piece,
            allowed_tags=allowed_tags,
            path=path,
            line_no=line_no,
            segment_no=segment_no,
            stats=stats,
        )
        if tag is not None and structurally_valid:
            tags.append(tag)
            if previous_tag == "O" and tag == "O":
                add_issue(
                    stats,
                    code="consecutive_o_segments",
                    path=path,
                    line_no=line_no,
                    segment_no=segment_no,
                    detail="consecutive O segments should usually be merged",
                    text=piece,
                )
            previous_tag = tag

    if tags and all(tag == "O" for tag in tags):
        add_issue(
            stats,
            code="line_has_only_o_tags",
            path=path,
            line_no=line_no,
            segment_no=None,
            detail="instruction says every line should contain at least one non-O agricultural entity",
            text=raw_line,
        )
    elif not tags:
        add_issue(
            stats,
            code="line_has_no_valid_segments",
            path=path,
            line_no=line_no,
            segment_no=None,
            detail="line produced no valid tagged segments",
            text=raw_line,
        )

    return stripped


def scan_path(input_path: Path, *, allowed_tags: set[str], check_duplicates: bool) -> ScanStats:
    stats = ScanStats()
    seen_lines: dict[str, tuple[Path, int]] = {}

    for path in iter_input_files(input_path):
        stats.files += 1
        with path.open("r", encoding="utf-8") as tagged_file:
            for line_no, line in enumerate(tagged_file, start=1):
                stats.lines += 1
                normalized_line = scan_line(
                    line,
                    allowed_tags=allowed_tags,
                    path=path,
                    line_no=line_no,
                    stats=stats,
                )
                if not check_duplicates or not normalized_line:
                    continue
                if normalized_line in seen_lines:
                    first_path, first_line = seen_lines[normalized_line]
                    add_issue(
                        stats,
                        code="duplicate_line",
                        path=path,
                        line_no=line_no,
                        segment_no=None,
                        detail=f"duplicates {first_path}:{first_line}",
                        text=normalized_line,
                    )
                else:
                    seen_lines[normalized_line] = (path, line_no)

    return stats


def print_summary(stats: ScanStats) -> None:
    print("ISSUE                       COUNT")
    print("--------------------------  -----")
    for code, count in sorted(stats.issue_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{code:<26}  {count:>5}")
    print()
    print(f"files: {stats.files}")
    print(f"lines: {stats.lines}")
    print(f"valid_segments_seen: {stats.segments}")
    print(f"total_issues: {sum(stats.issue_counts.values())}")


def print_issues(stats: ScanStats, *, limit: int | None, code_filter: set[str] | None) -> None:
    issues = [
        issue
        for issue in stats.issues
        if code_filter is None or issue.code in code_filter
    ]
    issues = sorted(
        issues,
        key=lambda issue: (
            ISSUE_PRIORITY.get(issue.code, 999),
            issue.path,
            issue.line,
            issue.segment or 0,
        ),
    )
    if limit is not None:
        issues = issues[:limit]

    for issue in issues:
        segment = "" if issue.segment is None else f":seg{issue.segment}"
        print(
            f"{issue.path}:{issue.line}{segment} "
            f"{issue.code} - {issue.detail} :: {visible(issue.text)}"
        )


def stats_to_json(stats: ScanStats) -> str:
    payload = {
        "files": stats.files,
        "lines": stats.lines,
        "valid_segments_seen": stats.segments,
        "total_issues": sum(stats.issue_counts.values()),
        "issue_counts": dict(sorted(stats.issue_counts.items())),
        "issues": [asdict(issue) for issue in stats.issues],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recursively find issues in Burmese `text@TAG|` tagged .txt files.",
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
        "--no-duplicates",
        action="store_true",
        help="Skip duplicate-line detection.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Print issue locations after the summary.",
    )
    parser.add_argument(
        "--code",
        action="append",
        help="Only show details for an issue code. Can be repeated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum detail rows to print with --details. Use 0 for all. Default: 200",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full results as JSON.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    allowed_tags = load_allowed_tags(args.instruction)
    stats = scan_path(
        args.input,
        allowed_tags=allowed_tags,
        check_duplicates=not args.no_duplicates,
    )

    if args.json:
        print(stats_to_json(stats))
        return 0

    print_summary(stats)
    if args.details:
        limit = None if args.limit == 0 else args.limit
        print()
        print_issues(stats, limit=limit, code_filter=set(args.code) if args.code else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
