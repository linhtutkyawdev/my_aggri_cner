#!/usr/bin/env python3
from pathlib import Path
import argparse

def normalize_sentence(line: str) -> str:
    return " ".join(line.strip().split())

def sanitize_file(input_path: Path, output_dir: Path, chunk_size: int = 1000):
    output_dir.mkdir(parents=True, exist_ok=True)

    seen = set()
    unique_lines = []

    with input_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            sentence = normalize_sentence(line)

            if not sentence:
                continue

            key = sentence.lower()

            if key not in seen:
                seen.add(key)
                unique_lines.append(sentence)

    for index in range(0, len(unique_lines), chunk_size):
        chunk = unique_lines[index:index + chunk_size]
        chunk_number = index // chunk_size + 1

        output_file = output_dir / f"chunk_{chunk_number:03}.txt"

        with output_file.open("w", encoding="utf-8") as f:
            f.write("\n".join(chunk) + "\n")

    print(f"Done. {len(unique_lines)} unique lines written into {output_dir}")

def main():
    parser = argparse.ArgumentParser(
        description="Remove duplicate sentences from a txt file and split into 1000-line chunks."
    )

    parser.add_argument("input", help="Input .txt file")
    parser.add_argument(
        "-o", "--output-dir",
        default="sanitized_chunks",
        help="Directory for output chunk files"
    )
    parser.add_argument(
        "-s", "--chunk-size",
        type=int,
        default=1000,
        help="Lines per chunk"
    )

    args = parser.parse_args()

    sanitize_file(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        chunk_size=args.chunk_size
    )

if __name__ == "__main__":
    main()