#!/usr/bin/env python3
"""Visualize `text@TAG|` token/segment occurrences in Burmese CNER files."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from tagged_to_bio import iter_input_files, load_allowed_tags, normalize_tag


@dataclass
class TokenStats:
    files: int = 0
    lines: int = 0
    segments: int = 0
    malformed_segments: int = 0
    unknown_tags: Counter[str] = field(default_factory=Counter)
    tags: Counter[str] = field(default_factory=Counter)
    tokens: Counter[str] = field(default_factory=Counter)
    tag_tokens: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    token_tags: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    per_file_lines: Counter[str] = field(default_factory=Counter)
    per_file_segments: Counter[str] = field(default_factory=Counter)
    per_file_tags: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def parse_line(
    line: str,
    *,
    allowed_tags: set[str],
    stats: TokenStats,
    include_o: bool,
    source: Path,
    line_no: int,
    strict: bool,
) -> None:
    for index, piece in enumerate(line.rstrip("\n").split("|"), start=1):
        if not piece:
            continue
        if "@" not in piece:
            message = f"{source}:{line_no}: segment {index} has no @TAG: {piece!r}"
            if strict:
                raise ValueError(message)
            warn(message)
            stats.malformed_segments += 1
            continue

        text, raw_tag = piece.rsplit("@", 1)
        text = text.strip()
        tag = normalize_tag(raw_tag.strip())

        if not text:
            message = f"{source}:{line_no}: segment {index} has empty text"
            if strict:
                raise ValueError(message)
            warn(message)
            stats.malformed_segments += 1
            continue

        if tag not in allowed_tags:
            message = f"{source}:{line_no}: unknown tag {tag!r} in segment {piece!r}"
            if strict:
                raise ValueError(message)
            warn(message)
            stats.unknown_tags[tag] += 1
            continue

        if tag == "O" and not include_o:
            continue

        source_name = str(source)
        stats.segments += 1
        stats.tags[tag] += 1
        stats.tokens[text] += 1
        stats.tag_tokens[tag][text] += 1
        stats.token_tags[text][tag] += 1
        stats.per_file_segments[source_name] += 1
        stats.per_file_tags[source_name][tag] += 1


def collect_stats(input_path: Path, *, allowed_tags: set[str], include_o: bool, strict: bool) -> TokenStats:
    stats = TokenStats()
    for path in iter_input_files(input_path):
        stats.files += 1
        with path.open("r", encoding="utf-8") as tagged_file:
            for line_no, line in enumerate(tagged_file, start=1):
                if not line.strip():
                    continue
                stats.lines += 1
                stats.per_file_lines[str(path)] += 1
                parse_line(
                    line,
                    allowed_tags=allowed_tags,
                    stats=stats,
                    include_o=include_o,
                    source=path,
                    line_no=line_no,
                    strict=strict,
                )
    return stats


def sorted_counter(counter: Counter[str], limit: int | None = None) -> list[tuple[str, int]]:
    rows = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return rows if limit is None else rows[:limit]


def ambiguous_tokens(stats: TokenStats, limit: int | None = None) -> list[tuple[str, int, Counter[str]]]:
    rows = [
        (token, sum(tags.values()), tags)
        for token, tags in stats.token_tags.items()
        if len(tags) > 1
    ]
    rows.sort(key=lambda item: (-item[1], item[0]))
    return rows if limit is None else rows[:limit]


def print_table(stats: TokenStats, *, limit: int) -> None:
    tag_rows = sorted_counter(stats.tags)
    tag_width = max([len("TAG"), *(len(tag) for tag, _ in tag_rows)], default=3)
    tag_count_width = max([len("COUNT"), *(len(str(count)) for _, count in tag_rows)], default=5)
    denominator = sum(stats.tags.values()) or 1

    print("TAG DISTRIBUTION")
    print(f"{'TAG':<{tag_width}}  {'COUNT':>{tag_count_width}}  PERCENT")
    print(f"{'-' * tag_width}  {'-' * tag_count_width}  -------")
    for tag, count in tag_rows:
        print(f"{tag:<{tag_width}}  {count:>{tag_count_width}}  {count / denominator * 100:6.2f}%")

    print()
    print("TOP TOKENS")
    rows = sorted_counter(stats.tokens, limit)
    token_width = min(max([len("TOKEN"), *(len(token) for token, _ in rows)], default=5), 52)
    count_width = max([len("COUNT"), *(len(str(count)) for _, count in rows)], default=5)

    print(f"{'TOKEN':<{token_width}}  {'COUNT':>{count_width}}  TAGS")
    print(f"{'-' * token_width}  {'-' * count_width}  ----")
    for token, count in rows:
        shown_token = token if len(token) <= token_width else f"{token[: token_width - 1]}…"
        tags = ", ".join(f"{tag}:{tag_count}" for tag, tag_count in sorted_counter(stats.token_tags[token]))
        print(f"{shown_token:<{token_width}}  {count:>{count_width}}  {tags}")

    print()
    print(f"files: {stats.files}")
    print(f"lines: {stats.lines}")
    print(f"counted_segments: {stats.segments}")
    print(f"unique_tokens: {len(stats.tokens)}")
    print(f"ambiguous_tokens: {len(ambiguous_tokens(stats))}")
    if stats.malformed_segments:
        print(f"malformed_segments: {stats.malformed_segments}")
    if stats.unknown_tags:
        unknown = ", ".join(f"{tag}={count}" for tag, count in sorted(stats.unknown_tags.items()))
        print(f"unknown_tags: {unknown}")


def write_csv(stats: TokenStats, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_segments = sum(stats.tokens.values()) or 1
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["token", "count", "percent", "tags", "tag_percentages"])
        for token, count in sorted_counter(stats.tokens):
            tags = "; ".join(f"{tag}:{tag_count}" for tag, tag_count in sorted_counter(stats.token_tags[token]))
            tag_percentages = "; ".join(
                f"{tag}:{tag_count / count * 100:.2f}%"
                for tag, tag_count in sorted_counter(stats.token_tags[token])
            )
            writer.writerow([token, count, f"{count / total_segments * 100:.2f}%", tags, tag_percentages])


def write_tag_csv(stats: TokenStats, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_segments = sum(stats.tags.values()) or 1
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["tag", "count", "percent", "unique_tokens"])
        for tag, count in sorted_counter(stats.tags):
            writer.writerow([tag, count, f"{count / total_segments * 100:.2f}%", len(stats.tag_tokens[tag])])


def write_json(stats: TokenStats, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "files": stats.files,
        "lines": stats.lines,
        "counted_segments": stats.segments,
        "unique_tokens": len(stats.tokens),
        "malformed_segments": stats.malformed_segments,
        "unknown_tags": dict(stats.unknown_tags),
        "tag_distribution": dict(sorted_counter(stats.tags)),
        "tokens": [
            {
                "token": token,
                "count": count,
                "tags": dict(sorted_counter(stats.token_tags[token])),
            }
            for token, count in sorted_counter(stats.tokens)
        ],
        "tags": {
            tag: [
                {"token": token, "count": count}
                for token, count in sorted_counter(counter)
            ]
            for tag, counter in sorted(stats.tag_tokens.items())
        },
        "ambiguous_tokens": [
            {
                "token": token,
                "count": count,
                "tags": dict(sorted_counter(tags)),
            }
            for token, count, tags in ambiguous_tokens(stats)
        ],
        "per_file": {
            path_name: {
                "lines": stats.per_file_lines[path_name],
                "counted_segments": stats.per_file_segments[path_name],
                "tags": dict(sorted_counter(stats.per_file_tags[path_name])),
            }
            for path_name in sorted(stats.per_file_lines)
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def bar_rows(rows: list[tuple[str, int]], *, max_count: int) -> str:
    rendered = []
    for token, count in rows:
        width = 0 if max_count == 0 else max(2, int(count / max_count * 100))
        rendered.append(
            f"""
            <div class="row">
              <div class="token" title="{html.escape(token)}">{html.escape(token)}</div>
              <div class="bar-wrap"><div class="bar" style="width:{width}%"></div></div>
              <div class="count">{count}</div>
            </div>
            """
        )
    return "\n".join(rendered)


def ambiguous_table(rows: list[tuple[str, int, Counter[str]]]) -> str:
    rendered = []
    for token, count, tags in rows:
        tag_text = ", ".join(f"{tag}:{tag_count}" for tag, tag_count in sorted_counter(tags))
        rendered.append(
            f"""
            <tr>
              <td title="{html.escape(token)}">{html.escape(token)}</td>
              <td class="num">{count}</td>
              <td>{html.escape(tag_text)}</td>
            </tr>
            """
        )
    if not rendered:
        return '<tr><td colspan="3">No multi-tag tokens found.</td></tr>'
    return "\n".join(rendered)


def per_file_table(stats: TokenStats) -> str:
    tags = [tag for tag, _ in sorted_counter(stats.tags)]
    header = "".join(f"<th>{html.escape(tag)}</th>" for tag in tags)
    rows = []
    for path_name in sorted(stats.per_file_lines):
        file_tags = stats.per_file_tags[path_name]
        tag_cells = "".join(f'<td class="num">{file_tags.get(tag, 0)}</td>' for tag in tags)
        rows.append(
            f"""
            <tr>
              <td title="{html.escape(path_name)}">{html.escape(Path(path_name).name)}</td>
              <td class="num">{stats.per_file_lines[path_name]}</td>
              <td class="num">{stats.per_file_segments[path_name]}</td>
              {tag_cells}
            </tr>
            """
        )
    return f"""
    <div class="table-scroll">
      <table>
        <thead>
          <tr><th>File</th><th>Lines</th><th>Segments</th>{header}</tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


def write_html(stats: TokenStats, path: Path, *, limit: int, per_tag_limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top_rows = sorted_counter(stats.tokens, limit)
    top_max = top_rows[0][1] if top_rows else 0
    tag_rows = sorted_counter(stats.tags)
    tag_max = tag_rows[0][1] if tag_rows else 0
    entity_segments = stats.segments - stats.tags.get("O", 0)
    o_segments = stats.tags.get("O", 0)
    ambiguous_rows = ambiguous_tokens(stats, limit)

    tag_sections = []
    for tag, counter in sorted(stats.tag_tokens.items()):
        rows = sorted_counter(counter, per_tag_limit)
        max_count = rows[0][1] if rows else 0
        tag_sections.append(
            f"""
            <section>
              <h2>{html.escape(tag)} <span>{sum(counter.values())} segments, {len(counter)} unique</span></h2>
              {bar_rows(rows, max_count=max_count)}
            </section>
            """
        )

    unknown = ""
    if stats.unknown_tags:
        unknown = "<p class=\"warn\">Unknown tags: " + html.escape(
            ", ".join(f"{tag}={count}" for tag, count in sorted(stats.unknown_tags.items()))
        ) + "</p>"

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Burmese CNER Token Occurrences</title>
  <style>
    body {{
      margin: 0;
      font-family: "Myanmar Text", "Noto Sans Myanmar", Arial, sans-serif;
      color: #1f2933;
      background: #f7faf7;
    }}
    header {{
      padding: 28px 36px;
      background: #1b5e20;
      color: white;
    }}
    h1 {{ margin: 0 0 10px; font-size: 28px; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 18px; }}
    .metric {{
      background: rgba(255, 255, 255, 0.14);
      border: 1px solid rgba(255, 255, 255, 0.22);
      border-radius: 8px;
      padding: 10px 14px;
      min-width: 130px;
    }}
    .metric strong {{ display: block; font-size: 22px; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    section {{
      background: white;
      border: 1px solid #dfe8dd;
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 22px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }}
    h2 {{ margin: 0 0 16px; font-size: 21px; color: #1b5e20; }}
    h2 span {{ color: #64748b; font-size: 14px; font-weight: normal; }}
    .row {{
      display: grid;
      grid-template-columns: minmax(180px, 36%) 1fr 70px;
      gap: 12px;
      align-items: center;
      padding: 6px 0;
      border-bottom: 1px solid #eef3ed;
    }}
    .row:last-child {{ border-bottom: none; }}
    .token {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 15px;
    }}
    .bar-wrap {{
      height: 18px;
      background: #ecf5e9;
      border-radius: 4px;
      overflow: hidden;
    }}
    .bar {{
      height: 100%;
      background: linear-gradient(90deg, #43a047, #00897b);
    }}
    .count {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .warn {{ color: #a15c00; font-weight: 600; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
    }}
    .mini-card {{
      border: 1px solid #e5eee2;
      border-radius: 8px;
      padding: 14px;
      background: #fbfdfb;
    }}
    .mini-card strong {{
      display: block;
      font-size: 24px;
      color: #1b5e20;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 8px 10px;
      border-bottom: 1px solid #eef3ed;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #edf7ed;
      color: #1b5e20;
      z-index: 1;
    }}
    .table-scroll {{
      max-height: 520px;
      overflow: auto;
      border: 1px solid #eef3ed;
      border-radius: 8px;
    }}
    @media (max-width: 760px) {{
      .row {{ grid-template-columns: 1fr 70px; }}
      .bar-wrap {{ grid-column: 1 / -1; grid-row: 2; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Burmese CNER Token Occurrences</h1>
    <div>Exact `text@TAG|` segment frequency visualization.</div>
    <div class="summary">
      <div class="metric"><strong>{stats.files}</strong>files</div>
      <div class="metric"><strong>{stats.lines}</strong>lines</div>
      <div class="metric"><strong>{stats.segments}</strong>segments</div>
      <div class="metric"><strong>{len(stats.tokens)}</strong>unique tokens</div>
    </div>
    {unknown}
  </header>
  <main>
    <section>
      <h2>Dataset Summary <span>counted mode</span></h2>
      <div class="grid">
        <div class="mini-card"><strong>{entity_segments}</strong>entity segments</div>
        <div class="mini-card"><strong>{o_segments}</strong>O segments</div>
        <div class="mini-card"><strong>{len(stats.tags)}</strong>tags present</div>
        <div class="mini-card"><strong>{len(ambiguous_tokens(stats))}</strong>multi-tag tokens</div>
      </div>
    </section>
    <section>
      <h2>Overall Tag Distribution <span>segments per tag</span></h2>
      {bar_rows(tag_rows, max_count=tag_max)}
    </section>
    <section>
      <h2>Top Tokens <span>overall</span></h2>
      {bar_rows(top_rows, max_count=top_max)}
    </section>
    <section>
      <h2>Tokens Appearing With Multiple Tags <span>possible consistency review list</span></h2>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Token</th><th>Total</th><th>Tags</th></tr></thead>
          <tbody>{ambiguous_table(ambiguous_rows)}</tbody>
        </table>
      </div>
    </section>
    <section>
      <h2>Per-File Tag Distribution <span>counts by source file</span></h2>
      {per_file_table(stats)}
    </section>
    {''.join(tag_sections)}
  </main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Count and visualize exact token/segment occurrences in `text@TAG|` files.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("fixed_tagged"),
        help="Tagged .txt file or directory. Default: fixed_tagged",
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
        help="Include O segments. Default: count entity-tagged segments only.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        help="Number of overall rows to print/render. Default: 50",
    )
    parser.add_argument(
        "--per-tag-top",
        type=int,
        default=30,
        help="Number of rows to render per tag in HTML. Default: 30",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=Path("reports/token_occurrences.html"),
        help="Write an HTML visualization report. Default: reports/token_occurrences.html",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional CSV output path.",
    )
    parser.add_argument(
        "--tag-csv",
        type=Path,
        help="Optional tag distribution CSV output path with count and percentage.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Optional JSON output path.",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Only print the terminal table; do not write HTML.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on the first malformed/unknown-tag segment. Default warns and skips it.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    allowed_tags = load_allowed_tags(args.instruction)
    stats = collect_stats(
        args.input,
        allowed_tags=allowed_tags,
        include_o=args.include_o,
        strict=args.strict,
    )

    print_table(stats, limit=args.top)

    if not args.no_html:
        write_html(stats, args.html, limit=args.top, per_tag_limit=args.per_tag_top)
        print(f"\nhtml_report: {args.html}")
    if args.csv:
        write_csv(stats, args.csv)
        print(f"csv: {args.csv}")
    if args.tag_csv:
        write_tag_csv(stats, args.tag_csv)
        print(f"tag_csv: {args.tag_csv}")
    if args.json:
        write_json(stats, args.json)
        print(f"json: {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
