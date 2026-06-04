#!/usr/bin/env python3
"""Find and fix common broken Burmese spellings in tagged CNER text files.

The tool is intentionally conservative:
- by default it only reports safe replacements and suspicious patterns;
- pass --apply to edit files in place, or -o/--output-dir to write copies;
- safe replacements never touch tags, only file text.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    from tagged_to_bio import iter_input_files
except ModuleNotFoundError:  # Allow running from repo root.
    from scripts.tagged_to_bio import iter_input_files


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    replacement: str
    reason: str


@dataclass(frozen=True)
class SuspiciousPattern:
    name: str
    pattern: re.Pattern[str]
    reason: str


@dataclass(frozen=True)
class Hit:
    path: Path
    line_no: int
    name: str
    before: str
    after: str | None
    reason: str


@dataclass
class Stats:
    files: int = 0
    changed_files: int = 0
    lines: int = 0
    changed_lines: int = 0
    safe_hits: int = 0
    suspicious_hits: int = 0
    hits: list[Hit] = field(default_factory=list)


SAFE_RULES: tuple[Rule, ...] = (
    Rule(
        name="merge_kilogram_qty",
        pattern=re.compile(r"ကီလို@QTY\|ဂရမ်"),
        replacement="ကီလိုဂရမ်@QTY|",
        reason="merge split kilogram unit inside QTY span",
    ),
    Rule(
        name="broken_nine_can",
        pattern=re.compile(r"န[ူိိူ]{2}င်"),
        replacement="နိုင်",
        reason="common broken spelling for နိုင်",
    ),
    Rule(
        name="broken_rate",
        pattern=re.compile(r"န[ူိိူ]{2}န်း"),
        replacement="နှုန်း",
        reason="common broken spelling for နှုန်း",
    ),
    Rule(
        name="broken_hpyit",
        pattern=re.compile(r"ဖြသ်"),
        replacement="ဖြစ်",
        reason="common typo for ဖြစ်",
    ),
    Rule(
        name="broken_spray",
        pattern=re.compile(r"ဖျန်(?!း)(?=ဆေး|တာ|ထား|မယ်|ပေး|သင့်|သင့်|ရင်|ပါ|လို့|နိုင်|ခြင်း|ပြီး)"),
        replacement="ဖျန်း",
        reason="common typo for ဖျန်း in spray contexts",
    ),
    Rule(
        name="broken_rate_plain",
        pattern=re.compile(r"နူန်း"),
        replacement="နှုန်း",
        reason="common typo for နှုန်း",
    ),
)


SUSPICIOUS_PATTERNS: tuple[SuspiciousPattern, ...] = (
    SuspiciousPattern(
        name="ui_vowel_order",
        pattern=re.compile(r"ူိ|ိူ"),
        reason="unusual Burmese vowel order; often OCR/typing damage",
    ),
    SuspiciousPattern(
        name="possible_missing_au",
        pattern=re.compile(r"(?<!ဖစ်ပရို)ဖစ်"),
        reason="often a typo for ဖြစ်, but can be part of names; review manually",
    ),
    SuspiciousPattern(
        name="latin_digit_in_text",
        pattern=re.compile(r"(?<=[\u1000-\u109f])[0-9]|[0-9](?=[\u1000-\u109f])"),
        reason="Latin digit is adjacent to Burmese text; normalize if needed",
    ),
)


def visible(text: str, limit: int = 160) -> str:
    text = text.strip()
    return text if len(text) <= limit else f"{text[:limit]}..."


def apply_safe_rules(line: str) -> tuple[str, list[tuple[Rule, str]]]:
    changed_line = line
    changes: list[tuple[Rule, str]] = []
    for rule in SAFE_RULES:
        next_line = rule.pattern.sub(rule.replacement, changed_line)
        if next_line != changed_line:
            changes.append((rule, next_line))
            changed_line = next_line
    return changed_line, changes


def output_path_for(input_file: Path, *, input_root: Path, output_dir: Path) -> Path:
    if input_root.is_file():
        return output_dir / input_file.name
    return output_dir / input_file.relative_to(input_root)


def scan_file(
    path: Path,
    *,
    input_root: Path,
    output_dir: Path | None,
    apply: bool,
    stats: Stats,
    show_suspicious: bool,
) -> None:
    stats.files += 1
    original_text = path.read_text(encoding="utf-8")
    had_trailing_newline = original_text.endswith("\n")
    original_lines = original_text.splitlines()
    fixed_lines: list[str] = []
    file_changed = False

    for line_no, line in enumerate(original_lines, start=1):
        stats.lines += 1
        fixed_line, changes = apply_safe_rules(line)
        fixed_lines.append(fixed_line)

        if changes:
            stats.safe_hits += len(changes)
            stats.changed_lines += int(fixed_line != line)
            file_changed = file_changed or fixed_line != line
            for rule, after in changes:
                stats.hits.append(
                    Hit(
                        path=path,
                        line_no=line_no,
                        name=rule.name,
                        before=visible(line),
                        after=visible(after),
                        reason=rule.reason,
                    )
                )

        if not show_suspicious:
            continue

        for suspicious in SUSPICIOUS_PATTERNS:
            if suspicious.pattern.search(fixed_line):
                stats.suspicious_hits += 1
                stats.hits.append(
                    Hit(
                        path=path,
                        line_no=line_no,
                        name=f"suspicious:{suspicious.name}",
                        before=visible(fixed_line),
                        after=None,
                        reason=suspicious.reason,
                    )
                )

    if not file_changed:
        return

    stats.changed_files += 1
    if not apply and output_dir is None:
        return

    fixed_text = "\n".join(fixed_lines)
    if had_trailing_newline:
        fixed_text += "\n"

    if output_dir is None:
        path.write_text(fixed_text, encoding="utf-8")
        return

    target = output_path_for(path, input_root=input_root, output_dir=output_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(fixed_text, encoding="utf-8")


def print_summary(stats: Stats, *, destination: str) -> None:
    print(f"destination: {destination}")
    print(f"files: {stats.files}")
    print(f"changed_files: {stats.changed_files}")
    print(f"lines: {stats.lines}")
    print(f"changed_lines: {stats.changed_lines}")
    print(f"safe_fix_hits: {stats.safe_hits}")
    print(f"suspicious_hits: {stats.suspicious_hits}")


def print_hits(stats: Stats, *, limit: int | None) -> None:
    hits = stats.hits if limit is None else stats.hits[:limit]
    if not hits:
        return

    print()
    for hit in hits:
        print(f"{hit.path}:{hit.line_no} {hit.name} - {hit.reason}")
        print(f"  before: {hit.before}")
        if hit.after is not None:
            print(f"  after:  {hit.after}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find and optionally fix common broken Burmese spellings in tagged .txt files.",
    )
    parser.add_argument("input", type=Path, help="Tagged .txt file or directory.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Edit files in place. Default only reports what would change.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Write fixed copies under this directory instead of editing in place.",
    )
    parser.add_argument(
        "--no-suspicious",
        action="store_true",
        help="Only show safe auto-fixes; skip suspicious-pattern review hits.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Print line-level hits.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum detail rows with --details. Use 0 for all. Default: 100",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.apply and args.output_dir is not None:
        parser.error("--apply and --output-dir are mutually exclusive")

    stats = Stats()
    for path in iter_input_files(args.input):
        scan_file(
            path,
            input_root=args.input,
            output_dir=args.output_dir,
            apply=args.apply or args.output_dir is not None,
            stats=stats,
            show_suspicious=not args.no_suspicious,
        )

    if args.output_dir is not None:
        destination = str(args.output_dir)
    elif args.apply:
        destination = "in-place"
    else:
        destination = "dry-run"
    print_summary(stats, destination=destination)

    if args.details:
        limit = None if args.limit == 0 else args.limit
        print_hits(stats, limit=limit)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
