#!/usr/bin/env python3
"""Parse NCRF++ evaluation logs into CSV and comparison charts."""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path


MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
LOSS_RE = re.compile(r"^totalloss:\s*([0-9.eE+-]+)\s*$", re.IGNORECASE)
TOKENS_RE = re.compile(
    r"^Right token\s*=\s*(\d+)\s+All token\s*=\s*(\d+)\s+acc\s*=\s*([0-9.eE+-]+)"
)
EVAL_RE = re.compile(
    r"^(Dev|Test):\s*time:\s*([0-9.eE+-]+)s,\s*"
    r"speed:\s*([0-9.eE+-]+)st/s;\s*"
    r"acc:\s*([0-9.eE+-]+),\s*p:\s*([0-9.eE+-]+),\s*"
    r"r:\s*([0-9.eE+-]+),\s*f:\s*([0-9.eE+-]+)\s*$",
    re.IGNORECASE,
)

COLORS = {
    "dev": "#2878B5",
    "test": "#D97706",
    "accuracy": "#6D5AA7",
    "precision": "#3B6EA8",
    "recall": "#4F8A5B",
    "f1": "#C94F55",
}
FONT_FAMILY = "'Times New Roman', 'Liberation Serif', Times, serif"


@dataclass
class SplitMetrics:
    right_tokens: int
    all_tokens: int
    token_accuracy: float
    time_seconds: float
    speed_st_per_s: float
    accuracy: float
    precision: float
    recall: float
    f1: float


@dataclass
class ModelResult:
    model: str
    total_loss: float | None = None
    dev: SplitMetrics | None = None
    test: SplitMetrics | None = None


def parse_results(text: str) -> list[ModelResult]:
    results: list[ModelResult] = []
    current: ModelResult | None = None
    pending_tokens: tuple[int, int, float] | None = None

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        if MODEL_RE.fullmatch(line) and not any(
            marker in line.lower()
            for marker in ("totalloss", "token", "time", "score", "model")
        ):
            if current is not None:
                results.append(current)
            current = ModelResult(model=line)
            pending_tokens = None
            continue

        if current is None:
            continue

        loss_match = LOSS_RE.match(line)
        if loss_match:
            current.total_loss = float(loss_match.group(1))
            continue

        tokens_match = TOKENS_RE.match(line)
        if tokens_match:
            pending_tokens = (
                int(tokens_match.group(1)),
                int(tokens_match.group(2)),
                float(tokens_match.group(3)),
            )
            continue

        eval_match = EVAL_RE.match(line)
        if eval_match:
            if pending_tokens is None:
                raise ValueError(
                    f"line {line_no}: {eval_match.group(1)} metrics have no "
                    "preceding 'Right token' line"
                )
            right_tokens, all_tokens, token_accuracy = pending_tokens
            metrics = SplitMetrics(
                right_tokens=right_tokens,
                all_tokens=all_tokens,
                token_accuracy=token_accuracy,
                time_seconds=float(eval_match.group(2)),
                speed_st_per_s=float(eval_match.group(3)),
                accuracy=float(eval_match.group(4)),
                precision=float(eval_match.group(5)),
                recall=float(eval_match.group(6)),
                f1=float(eval_match.group(7)),
            )
            split = eval_match.group(1).lower()
            setattr(current, split, metrics)
            pending_tokens = None

    if current is not None:
        results.append(current)

    if not results:
        raise ValueError("no model result blocks were found")

    names: set[str] = set()
    for result in results:
        if result.model in names:
            raise ValueError(f"duplicate model block: {result.model}")
        names.add(result.model)
        missing = [
            field
            for field, value in (
                ("totalloss", result.total_loss),
                ("Dev metrics", result.dev),
                ("Test metrics", result.test),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                f"{result.model}: missing {', '.join(missing)}"
            )

    return results


def write_csv(results: list[ModelResult], path: Path) -> None:
    fields = [
        "model",
        "total_loss",
        "dev_right_tokens",
        "dev_all_tokens",
        "dev_token_accuracy",
        "dev_time_seconds",
        "dev_speed_st_per_s",
        "dev_accuracy",
        "dev_precision",
        "dev_recall",
        "dev_f1",
        "test_right_tokens",
        "test_all_tokens",
        "test_token_accuracy",
        "test_time_seconds",
        "test_speed_st_per_s",
        "test_accuracy",
        "test_precision",
        "test_recall",
        "test_f1",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for result in results:
            assert result.dev is not None and result.test is not None
            row: dict[str, str | int | float] = {
                "model": result.model,
                "total_loss": result.total_loss or 0.0,
            }
            for split_name, metrics in (("dev", result.dev), ("test", result.test)):
                for field in SplitMetrics.__dataclass_fields__:
                    row[f"{split_name}_{field}"] = getattr(metrics, field)
            writer.writerow(row)


def svg_header(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">'
        ),
        (
            f'<text x="95" y="76" font-family="{FONT_FAMILY}" '
            f'font-size="38" font-weight="700" fill="#101828">{escape(title)}</text>'
        ),
        (
            f'<text x="95" y="112" font-family="{FONT_FAMILY}" '
            f'font-size="20" fill="#475467">{escape(subtitle)}</text>'
        ),
    ]


def display_model_label(model: str) -> tuple[str, str]:
    parts = model.lower().split("_")
    scheme = parts[0].upper()
    unit = "Syllable" if "syllable" in parts else "Word"
    embedding = "With Embeddings" if "emb" in parts else "Without Embeddings"
    return f"{scheme} {unit}", embedding


def write_grouped_bar_chart(
    path: Path,
    results: list[ModelResult],
    *,
    title: str,
    subtitle: str,
    series: list[tuple[str, str, list[float]]],
    minimum: float,
    maximum: float,
    value_format: str,
) -> None:
    width = 1800
    height = 1000
    left, right, top, bottom = 125, 65, 205, 150
    plot_width = width - left - right
    plot_height = height - top - bottom
    svg = svg_header(width, height, title, subtitle)

    tick_count = 5
    for index in range(tick_count + 1):
        value = minimum + (maximum - minimum) * index / tick_count
        y = top + plot_height - plot_height * index / tick_count
        svg.extend(
            [
                f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" '
                f'y2="{y:.1f}" stroke="#E5E7EB" stroke-width="1"/>',
                f'<text x="{left - 14}" y="{y + 5:.1f}" text-anchor="end" '
                f'font-family="{FONT_FAMILY}" '
                f'font-size="17" fill="#475467">{value_format.format(value)}</text>',
            ]
        )
    svg.append(
        f'<line x1="{left}" y1="{top + plot_height}" '
        f'x2="{left + plot_width}" y2="{top + plot_height}" '
        'stroke="#98A2B3" stroke-width="1.5"/>'
    )

    series_count = len(series)
    group_width = plot_width / len(results)
    inner_width = group_width * 0.70
    bar_gap = 6
    bar_width = (inner_width - bar_gap * (series_count - 1)) / series_count
    for model_index, result in enumerate(results):
        group_x = left + model_index * group_width
        bars_x = group_x + (group_width - inner_width) / 2
        label_x = group_x + group_width / 2
        label_line_1, label_line_2 = display_model_label(result.model)
        svg.append(
            f'<text x="{label_x:.1f}" y="{top + plot_height + 36}" '
            f'text-anchor="middle" font-family="{FONT_FAMILY}" '
            f'font-size="18" font-weight="700" fill="#1D2939">'
            f'<tspan x="{label_x:.1f}">{escape(label_line_1)}</tspan>'
            f'<tspan x="{label_x:.1f}" dy="25" font-size="16" '
            f'font-weight="400" fill="#475467">{escape(label_line_2)}</tspan>'
            "</text>"
        )
        for series_index, (_, color, values) in enumerate(series):
            value = values[model_index]
            normalized = max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))
            rendered_height = normalized * plot_height
            x = bars_x + series_index * (bar_width + bar_gap)
            y = top + plot_height - rendered_height
            svg.extend(
                [
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
                    f'height="{rendered_height:.1f}" rx="3" fill="{color}"/>',
                    f'<text x="{x + bar_width / 2:.1f}" y="{y - 8:.1f}" '
                    f'text-anchor="middle" font-family="{FONT_FAMILY}" '
                    f'font-size="16" font-weight="700" fill="#1D2939">'
                    f'{value_format.format(value)}</text>',
                ]
            )

    legend_item_width = 175
    legend_x = 95
    for index, (label, color, _) in enumerate(series):
        x = legend_x + index * legend_item_width
        svg.extend(
            [
                f'<rect x="{x}" y="137" width="17" height="17" rx="2" fill="{color}"/>',
                f'<text x="{x + 27}" y="152" '
                f'font-family="{FONT_FAMILY}" font-size="18" '
                f'fill="#344054">{escape(label)}</text>',
            ]
        )
    svg.append("</svg>")
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def render_png(svg_path: Path, png_path: Path) -> None:
    renderer = shutil.which("rsvg-convert")
    if renderer:
        subprocess.run(
            [renderer, str(svg_path), "-o", str(png_path)],
            check=True,
        )
        return

    renderer = shutil.which("magick") or shutil.which("convert")
    if renderer:
        subprocess.run([renderer, str(svg_path), str(png_path)], check=True)
        return

    raise RuntimeError(
        "PNG rendering requires rsvg-convert or ImageMagick (magick/convert)"
    )


def generate_charts(results: list[ModelResult], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        assert result.dev is not None and result.test is not None

    chart_specs = [
        (
            "test_aprf_comparison",
            "Test Accuracy, Precision, Recall, and F1",
            "Test-set APRF metrics for each model configuration",
            [
                (
                    "Accuracy",
                    COLORS["accuracy"],
                    [result.test.accuracy for result in results],
                ),
                (
                    "Precision",
                    COLORS["precision"],
                    [result.test.precision for result in results],
                ),
                (
                    "Recall",
                    COLORS["recall"],
                    [result.test.recall for result in results],
                ),
                ("F1", COLORS["f1"], [result.test.f1 for result in results]),
            ],
            0.65,
            0.95,
            "{:.3f}",
        ),
        (
            "test_inference_speed_comparison",
            "Test Inference Speed by Model",
            "Test-set sentences processed per second",
            [
                (
                    "Test speed",
                    COLORS["test"],
                    [result.test.speed_st_per_s for result in results],
                ),
            ],
            0.0,
            max(
                result.test.speed_st_per_s for result in results
            )
            * 1.12,
            "{:.0f}",
        ),
    ]

    png_paths: list[Path] = []
    for name, title, subtitle, series, minimum, maximum, value_format in chart_specs:
        svg_path = output_dir / f"{name}.svg"
        png_path = output_dir / f"{name}.png"
        write_grouped_bar_chart(
            svg_path,
            results,
            title=title,
            subtitle=subtitle,
            series=series,
            minimum=minimum,
            maximum=maximum,
            value_format=value_format,
        )
        render_png(svg_path, png_path)
        png_paths.append(png_path)
    return png_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert NCRF++ result logs to CSV and PNG comparison charts."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Text file containing one or more NCRF++ model result blocks.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("reports/ncrfpp_results"),
        help="Output directory. Default: reports/ncrfpp_results",
    )
    parser.add_argument(
        "--csv-name",
        default="model_results.csv",
        help="CSV filename inside the output directory.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        text = args.input.read_text(encoding="utf-8-sig")
        results = parse_results(text)
        csv_path = args.output_dir / args.csv_name
        write_csv(results, csv_path)
        png_paths = generate_charts(results, args.output_dir)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    best = max(results, key=lambda result: result.test.f1 if result.test else -1)
    assert best.test is not None
    print(f"Wrote {len(results)} model rows to {csv_path}")
    print(f"Generated {len(png_paths)} PNG charts in {args.output_dir}")
    print(f"Best test F1: {best.model} ({best.test.f1:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
