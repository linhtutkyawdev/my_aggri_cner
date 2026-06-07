#!/usr/bin/env python3
"""Export tag definitions from INSTRUCTION.MD to CSV."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


TAG_DEFINITION_START = "# Tag definitions"
TAG_DEFINITION_END = "# Important distinction rules"
TAG_HEADING_RE = re.compile(r"^([A-Z][A-Z_]*):$")


def clean_text(text: str) -> str:
    return " ".join(text.split())


def parse_tag_definitions(instruction_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {
            "tag": "O",
            "description": "Outside tag for non-entity text, grammar, punctuation, filler, and other text that is not part of an agricultural concept span.",
            "example": "တွင်, နှင့်, ။",
        }
    ]
    current: dict[str, str] | None = None
    description_lines: list[str] = []
    examples = ""
    in_definitions = False

    for raw_line in instruction_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == TAG_DEFINITION_START:
            in_definitions = True
            continue
        if line == TAG_DEFINITION_END and in_definitions:
            break
        if not in_definitions:
            continue

        heading = TAG_HEADING_RE.match(line)
        if heading:
            if current is not None:
                current["description"] = clean_text(" ".join(description_lines))
                current["example"] = clean_text(examples.removeprefix("Examples:").strip())
                rows.append(current)
            current = {"tag": heading.group(1), "description": "", "example": ""}
            description_lines = []
            examples = ""
            continue

        if current is None or not line:
            continue

        if line.startswith("Examples:"):
            examples = line
        elif examples:
            examples = f"{examples} {line}"
        else:
            description_lines.append(line)

    if current is not None:
        current["description"] = clean_text(" ".join(description_lines))
        current["example"] = clean_text(examples.removeprefix("Examples:").strip())
        rows.append(current)

    return rows


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["tag", "description", "example"])
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export tag definitions from INSTRUCTION.MD to CSV.")
    parser.add_argument(
        "--instruction",
        type=Path,
        default=Path("INSTRUCTION.MD"),
        help="Instruction markdown file. Default: INSTRUCTION.MD",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/tag_definitions.csv"),
        help="Output CSV path. Default: reports/tag_definitions.csv",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rows = parse_tag_definitions(args.instruction)
    write_csv(rows, args.output)
    print(f"wrote {len(rows)} tag definitions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
