#!/usr/bin/env python3
"""Compare reply length with and without Lembas.

Usage: python3 scripts/count_tokens.py evals/results/v1.0.0

Each eval folder holds baseline.md (no skill) and lembas.md (skill active).
Tokens are estimated as characters / 4. That is close enough for comparing
percentages. Pass --tiktoken to use the cl100k_base tokenizer if installed.
"""
import argparse
import pathlib
import sys


def make_counter(use_tiktoken):
    if use_tiktoken:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return lambda text: len(enc.encode(text))
    return lambda text: round(len(text) / 4)


def cut(base, lembas):
    """How much shorter the lembas reply is, as a percentage. An empty baseline has nothing to cut."""
    return f"{100 * (1 - lembas / base):6.1f}%" if base else f"{'n/a':>7}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir")
    parser.add_argument("--tiktoken", action="store_true")
    args = parser.parse_args()
    count = make_counter(args.tiktoken)

    root = pathlib.Path(args.results_dir)
    folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    if not folders:
        print(f"count_tokens: no eval folders in {root}", file=sys.stderr)
        sys.exit(1)

    total_base = total_lembas = 0
    missing = []
    print(f"{'eval':32} {'baseline':>8} {'lembas':>7} {'cut':>7}")
    for folder in folders:
        files = [folder / "baseline.md", folder / "lembas.md"]
        gone = [f for f in files if not f.is_file()]
        if gone:
            missing += gone
            continue
        base, lembas = (count(f.read_text(encoding="utf-8")) for f in files)
        total_base += base
        total_lembas += lembas
        print(f"{folder.name:32} {base:8} {lembas:7} {cut(base, lembas)}")
    print(f"{'TOTAL':32} {total_base:8} {total_lembas:7} {cut(total_base, total_lembas)}")
    if missing:
        print("count_tokens: missing reply files, left out of the totals:\n  " +
              "\n  ".join(str(f.relative_to(root)) for f in missing), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
