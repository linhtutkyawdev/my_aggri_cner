#!/usr/bin/env python3
"""Build Burmese token embeddings for NCRF++ from raw text files.

The script combines all .txt files in an input directory, tokenizes each
non-empty line with Pyidaungsu, trains fastText vectors, and writes the
headerless embedding format expected by NCRF++.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Burmese word/syllable embeddings from raw .txt files."
    )
    parser.add_argument(
        "--input-dir",
        default="raw/emb_txt",
        help="Directory containing raw .txt files. Default: raw/emb_txt",
    )
    parser.add_argument(
        "--mode",
        choices=("word", "syllable"),
        default="word",
        help="Pyidaungsu tokenization unit. Default: word",
    )
    parser.add_argument(
        "--out-dir",
        default="embeddings",
        help="Directory for tokenized corpus and embedding files. Default: embeddings",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Output basename. Default: burmese_agri_<mode>",
    )
    parser.add_argument("--dim", type=int, default=200, help="Embedding size.")
    parser.add_argument("--epoch", type=int, default=20, help="fastText epochs.")
    parser.add_argument("--min-count", type=int, default=2, help="Minimum token count.")
    parser.add_argument(
        "--model",
        choices=("skipgram", "cbow"),
        default="skipgram",
        help="fastText training model. Default: skipgram",
    )
    parser.add_argument(
        "--word-ngrams",
        type=int,
        default=2,
        help="fastText wordNgrams value. Default: 2",
    )
    parser.add_argument(
        "--minn",
        type=int,
        default=2,
        help="fastText minimum char ngram length. Default: 2",
    )
    parser.add_argument(
        "--maxn",
        type=int,
        default=5,
        help="fastText maximum char ngram length. Default: 5",
    )
    parser.add_argument(
        "--fasttext-bin",
        default="fasttext",
        help="Path/name of fastText CLI binary. Default: fasttext",
    )
    parser.add_argument(
        "--tokenized-only",
        action="store_true",
        help="Only write the tokenized corpus; do not train embeddings.",
    )
    return parser.parse_args()


def load_pyidaungsu():
    try:
        import pyidaungsu  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Pyidaungsu is not installed. Install it in this environment first, "
            "for example: pip install pyidaungsu"
        ) from exc
    return pyidaungsu


def tokenize(pyidaungsu, text: str, mode: str) -> List[str]:
    """Call Pyidaungsu while tolerating small API differences by version."""
    calls = [
        lambda: pyidaungsu.tokenize(text, form=mode),
        lambda: pyidaungsu.tokenize(text, mode),
    ]

    if mode == "word":
        for name in ("word_tokenize", "word_tokenizer"):
            if hasattr(pyidaungsu, name):
                calls.append(lambda name=name: getattr(pyidaungsu, name)(text))
    else:
        for name in ("syllable_tokenize", "syllable_tokenizer"):
            if hasattr(pyidaungsu, name):
                calls.append(lambda name=name: getattr(pyidaungsu, name)(text))

    last_error = None
    for call in calls:
        try:
            tokens = call()
        except (AttributeError, TypeError, ValueError) as exc:
            last_error = exc
            continue

        if isinstance(tokens, str):
            return [token for token in tokens.split() if token]
        return [str(token) for token in tokens if str(token).strip()]

    raise RuntimeError(
        f"Could not tokenize with Pyidaungsu mode={mode!r}. Last error: {last_error}"
    )


def iter_text_files(input_dir: Path) -> Iterable[Path]:
    yield from sorted(path for path in input_dir.rglob("*.txt") if path.is_file())


def write_tokenized_corpus(
    pyidaungsu, files: Iterable[Path], mode: str, output_path: Path
) -> int:
    line_count = 0
    with output_path.open("w", encoding="utf-8") as output_file:
        for file_path in files:
            with file_path.open("r", encoding="utf-8-sig") as input_file:
                for raw_line in input_file:
                    line = raw_line.strip()
                    if not line:
                        continue
                    tokens = tokenize(pyidaungsu, line, mode)
                    if tokens:
                        output_file.write(" ".join(tokens) + "\n")
                        line_count += 1
    return line_count


def run_fasttext(args: argparse.Namespace, corpus_path: Path, model_prefix: Path) -> None:
    fasttext_path = shutil.which(args.fasttext_bin)
    if fasttext_path is None:
        explicit_path = Path(args.fasttext_bin)
        if explicit_path.exists():
            fasttext_path = str(explicit_path)
        else:
            raise SystemExit(
                "fastText CLI was not found. Install fastText or pass its path with "
                "--fasttext-bin /path/to/fasttext"
            )
    command = [
        fasttext_path,
        args.model,
        "-input",
        str(corpus_path),
        "-output",
        str(model_prefix),
        "-dim",
        str(args.dim),
        "-epoch",
        str(args.epoch),
        "-minCount",
        str(args.min_count),
        "-wordNgrams",
        str(args.word_ngrams),
        "-minn",
        str(args.minn),
        "-maxn",
        str(args.maxn),
    ]
    subprocess.run(command, check=True)


def strip_fasttext_header(vec_path: Path, emb_path: Path) -> int:
    line_count = 0
    with vec_path.open("r", encoding="utf-8") as vec_file:
        with emb_path.open("w", encoding="utf-8") as emb_file:
            for line_number, line in enumerate(vec_file):
                if line_number == 0:
                    continue
                emb_file.write(line)
                line_count += 1
    return line_count


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    name = args.name or f"burmese_agri_{args.mode}"

    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")

    text_files = list(iter_text_files(input_dir))
    if not text_files:
        raise SystemExit(f"No .txt files found under: {input_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = out_dir / f"{name}.tokenized.txt"
    model_prefix = out_dir / name
    vec_path = out_dir / f"{name}.vec"
    emb_path = out_dir / f"{name}.emb"

    pyidaungsu = load_pyidaungsu()
    line_count = write_tokenized_corpus(pyidaungsu, text_files, args.mode, corpus_path)
    print(f"Tokenized {line_count} lines from {len(text_files)} files.")
    print(f"Tokenized corpus: {corpus_path}")

    if args.tokenized_only:
        return 0

    run_fasttext(args, corpus_path, model_prefix)
    vector_count = strip_fasttext_header(vec_path, emb_path)
    print(f"NCRF++ embedding file: {emb_path}")
    print(f"Vectors written: {vector_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
