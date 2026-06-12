#!/usr/bin/env python3
"""Create a train/dev/test entity-tag distribution report from CoNLL files."""

from __future__ import annotations

import argparse
import colorsys
import csv
import math
from collections import Counter
from html import escape
from pathlib import Path


SPLITS = ("train", "dev", "test")
VALID_PREFIXES = {"B", "I", "E", "S"}
FONT_FAMILY = "'Times New Roman', 'Liberation Serif', Times, serif"
CHART_COLORS = (
    "#173F5F",
    "#20639B",
    "#3CAEA3",
    "#2A9D8F",
    "#72B01D",
    "#F6C85F",
    "#F4A261",
    "#ED553B",
    "#D45087",
    "#955196",
    "#665191",
    "#4D5D53",
    "#B7B7A4",
)


def parse_label(label: str, path: Path, line_no: int) -> tuple[str, str] | None:
    if label == "O":
        return None

    try:
        prefix, tag = label.split("-", 1)
    except ValueError as error:
        raise ValueError(
            f"{path}:{line_no}: invalid label {label!r}; expected O or PREFIX-TAG"
        ) from error

    if prefix not in VALID_PREFIXES or not tag:
        raise ValueError(
            f"{path}:{line_no}: invalid label {label!r}; "
            "prefix must be B, I, E, or S"
        )
    return prefix, tag


def count_entities(path: Path) -> Counter[str]:
    """Count entity spans in one BIO or BIOES CoNLL file."""
    counts: Counter[str] = Counter()
    active_tag: str | None = None

    with path.open("r", encoding="utf-8-sig") as conll_file:
        for line_no, raw_line in enumerate(conll_file, start=1):
            line = raw_line.strip()
            if not line:
                active_tag = None
                continue

            columns = line.split()
            if len(columns) < 2:
                raise ValueError(
                    f"{path}:{line_no}: expected at least a token and a label"
                )

            parsed = parse_label(columns[-1], path, line_no)
            if parsed is None:
                active_tag = None
                continue

            prefix, tag = parsed
            if prefix in {"B", "S"}:
                counts[tag] += 1
                active_tag = tag if prefix == "B" else None
            elif active_tag != tag:
                raise ValueError(
                    f"{path}:{line_no}: {prefix}-{tag} does not continue "
                    f"an active {tag} entity"
                )
            elif prefix == "E":
                active_tag = None

    return counts


def find_split_files(folder: Path, split: str) -> list[Path]:
    return sorted(
        path
        for path in folder.glob(f"{split}.*.conll")
        if path.is_file()
    )


def build_report(folder: Path) -> dict[str, Counter[str]]:
    if not folder.is_dir():
        raise ValueError(f"input folder does not exist or is not a directory: {folder}")

    report: dict[str, Counter[str]] = {}
    for split in SPLITS:
        paths = find_split_files(folder, split)
        if not paths:
            raise ValueError(
                f"no {split}.*.conll files found in input folder: {folder}"
            )

        split_counts: Counter[str] = Counter()
        for path in paths:
            split_counts.update(count_entities(path))
        report[split] = split_counts

    return report


def write_csv(report: dict[str, Counter[str]], output_path: Path) -> None:
    tags = sorted(
        set().union(*(report[split] for split in SPLITS)),
        key=lambda tag: (-sum(report[split][tag] for split in SPLITS), tag),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            ["tag", "train_count", "dev_count", "test_count", "total_count"]
        )
        for tag in tags:
            split_counts = [report[split][tag] for split in SPLITS]
            writer.writerow([tag, *split_counts, sum(split_counts)])


def polar_point(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    radians = math.radians(angle - 90)
    return cx + radius * math.cos(radians), cy + radius * math.sin(radians)


def donut_segment(
    cx: float,
    cy: float,
    outer_radius: float,
    inner_radius: float,
    start_angle: float,
    end_angle: float,
) -> str:
    outer_start = polar_point(cx, cy, outer_radius, start_angle)
    outer_end = polar_point(cx, cy, outer_radius, end_angle)
    inner_end = polar_point(cx, cy, inner_radius, end_angle)
    inner_start = polar_point(cx, cy, inner_radius, start_angle)
    large_arc = 1 if end_angle - start_angle > 180 else 0
    return (
        f"M {outer_start[0]:.2f} {outer_start[1]:.2f} "
        f"A {outer_radius} {outer_radius} 0 {large_arc} 1 "
        f"{outer_end[0]:.2f} {outer_end[1]:.2f} "
        f"L {inner_end[0]:.2f} {inner_end[1]:.2f} "
        f"A {inner_radius} {inner_radius} 0 {large_arc} 0 "
        f"{inner_start[0]:.2f} {inner_start[1]:.2f} Z"
    )


def pie_segment(
    cx: float,
    cy: float,
    radius: float,
    start_angle: float,
    end_angle: float,
) -> str:
    start = polar_point(cx, cy, radius, start_angle)
    end = polar_point(cx, cy, radius, end_angle)
    large_arc = 1 if end_angle - start_angle > 180 else 0
    return (
        f"M {cx} {cy} L {start[0]:.2f} {start[1]:.2f} "
        f"A {radius} {radius} 0 {large_arc} 1 {end[0]:.2f} {end[1]:.2f} Z"
    )


def all_tags_color(index: int) -> str:
    """Return a distinct, deterministic color suitable for a large legend."""
    hue = (index * 0.61803398875) % 1.0
    saturation = 0.58 + (index % 3) * 0.08
    lightness = 0.43 + (index % 4) * 0.045
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{round(red * 255):02X}{round(green * 255):02X}{round(blue * 255):02X}"


def tag_totals(report: dict[str, Counter[str]]) -> Counter[str]:
    return Counter(
        {
            tag: sum(report[split][tag] for split in SPLITS)
            for tag in set().union(*(report[split] for split in SPLITS))
        }
    )


def write_pie_chart(
    report: dict[str, Counter[str]],
    output_path: Path,
    *,
    visible_tags: int = 12,
) -> None:
    totals = tag_totals(report)
    ranked = totals.most_common()
    slices = ranked[:visible_tags]
    remaining = ranked[visible_tags:]
    if remaining:
        slices.append((f"OTHER ({len(remaining)} tags)", sum(count for _, count in remaining)))

    grand_total = sum(totals.values())
    if not grand_total:
        raise ValueError("cannot create a pie chart because the total entity count is zero")

    width, height = 1440, 960
    cx, cy = 400, 530
    outer_radius, inner_radius = 285, 165
    title = "Entity Tag Distribution"
    subtitle = "Total entity spans across train, development, and test sets"
    svg: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            'role="img" aria-labelledby="title description">'
        ),
        f"<title id=\"title\">{title}</title>",
        f"<desc id=\"description\">{subtitle}</desc>",
        f'<text x="76" y="98" font-family="{FONT_FAMILY}" font-size="34" '
        f'font-weight="700" fill="#172B4D">{title}</text>',
        f'<text x="76" y="134" font-family="{FONT_FAMILY}" font-size="17" '
        f'fill="#6B778C">{subtitle}</text>',
    ]

    start_angle = 0.0
    for index, (_, count) in enumerate(slices):
        end_angle = start_angle + count / grand_total * 360
        path = donut_segment(
            cx, cy, outer_radius, inner_radius, start_angle, end_angle
        )
        svg.append(
            f'<path d="{path}" fill="{CHART_COLORS[index]}" stroke="#FFFFFF" '
            'stroke-width="3"/>'
        )
        start_angle = end_angle

    svg.extend(
        [
            f'<text x="{cx}" y="{cy - 10}" text-anchor="middle" '
            f'font-family="{FONT_FAMILY}" font-size="18" font-weight="600" '
            'fill="#6B778C">TOTAL ENTITIES</text>',
            f'<text x="{cx}" y="{cy + 38}" text-anchor="middle" '
            f'font-family="{FONT_FAMILY}" font-size="39" font-weight="700" '
            f'fill="#172B4D">{grand_total:,}</text>',
            f'<text x="770" y="286" font-family="{FONT_FAMILY}" font-size="15" '
            'font-weight="700" letter-spacing="1.2" fill="#6B778C">'
            "TAG BREAKDOWN</text>",
        ]
    )

    for index, (tag, count) in enumerate(slices):
        y = 326 + index * 43
        percentage = count / grand_total * 100
        svg.extend(
            [
                f'<rect x="770" y="{y - 16}" width="18" height="18" rx="4" '
                f'fill="{CHART_COLORS[index]}"/>',
                f'<text x="804" y="{y}" font-family="{FONT_FAMILY}" '
                f'font-size="17" font-weight="600" fill="#253858">{escape(tag)}</text>',
                f'<text x="1180" y="{y}" text-anchor="end" '
                f'font-family="{FONT_FAMILY}" font-size="16" '
                f'fill="#42526E">{count:,}</text>',
                f'<text x="1304" y="{y}" text-anchor="end" '
                f'font-family="{FONT_FAMILY}" font-size="16" '
                f'font-weight="600" fill="#172B4D">{percentage:.2f}%</text>',
            ]
        )

    svg.extend(
        [
            '<line x1="770" y1="898" x2="1304" y2="898" stroke="#DFE1E6"/>',
            f'<text x="770" y="925" font-family="{FONT_FAMILY}" font-size="13" '
            'fill="#8993A4">Smaller categories are grouped for chart readability. '
            "The table contains all tags.</text>",
            "</svg>",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def write_all_tags_pie_chart(
    report: dict[str, Counter[str]],
    output_path: Path,
) -> None:
    """Write a minimalist pie chart containing every tag and no numeric labels."""
    totals = tag_totals(report)
    slices = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    grand_total = sum(totals.values())
    if not grand_total:
        raise ValueError("cannot create a pie chart because the total entity count is zero")

    width, height = 1440, 960
    cx, cy, radius = 375, 530, 315
    svg: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            'role="img" aria-label="Pie chart of all entity tags">'
        ),
    ]

    start_angle = 0.0
    for index, (_, count) in enumerate(slices):
        end_angle = start_angle + count / grand_total * 360
        svg.append(
            f'<path d="{pie_segment(cx, cy, radius, start_angle, end_angle)}" '
            f'fill="{all_tags_color(index)}" stroke="#FFFFFF" stroke-width="1.5"/>'
        )
        start_angle = end_angle

    rows_per_column = math.ceil(len(slices) / 2)
    for index, (tag, _) in enumerate(slices):
        column = index // rows_per_column
        row = index % rows_per_column
        x = 760 + column * 315
        y = 246 + row * 37
        color = all_tags_color(index)
        svg.extend(
            [
                f'<rect x="{x}" y="{y - 15}" width="18" height="18" rx="3" '
                f'fill="{color}"/>',
                f'<text x="{x + 32}" y="{y}" font-family="{FONT_FAMILY}" '
                f'font-size="17" font-weight="600" fill="#253858">{escape(tag)}</text>',
            ]
        )

    svg.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Count BIO/BIOES entity spans in train, dev, and test CoNLL files."
        )
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="Folder containing train.*.conll, dev.*.conll, and test.*.conll files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output CSV path. Default: <folder>/tag_distribution_report.csv",
    )
    parser.add_argument(
        "--chart",
        type=Path,
        help=(
            "Output SVG chart path. Default: "
            "<folder>/tag_distribution_pie_chart.svg"
        ),
    )
    parser.add_argument(
        "--all-tags-chart",
        action="store_true",
        help=(
            "Also create a minimalist 35-slice pie chart containing every tag, "
            "with a color legend and no counts or title."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_path = args.output or args.folder / "tag_distribution_report.csv"
    chart_path = args.chart or args.folder / "tag_distribution_pie_chart.svg"
    all_tags_chart_path = (
        args.folder / "tag_distribution_all_tags_pie_chart.svg"
    )

    try:
        report = build_report(args.folder)
        write_csv(report, output_path)
        write_pie_chart(report, chart_path)
        if args.all_tags_chart:
            write_all_tags_pie_chart(report, all_tags_chart_path)
    except (OSError, ValueError) as error:
        raise SystemExit(f"error: {error}") from error

    tag_count = len(set().union(*(report[split] for split in SPLITS)))
    print(f"Wrote {tag_count} entity tags to {output_path}")
    print(f"Wrote total-count distribution chart to {chart_path}")
    if args.all_tags_chart:
        print(f"Wrote all-tags distribution chart to {all_tags_chart_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
