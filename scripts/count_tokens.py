#!/usr/bin/env python3
"""Compare reply length with and without Lembas.

Usage: python3 scripts/count_tokens.py evals/results/v1.0.0

Each eval folder holds baseline.md (no skill) and lembas.md (skill active).
Tokens are estimated as characters / 4. That is close enough for comparing
percentages. Pass --tiktoken to use the cl100k_base tokenizer if installed.
"""
import argparse
import pathlib


def make_counter(use_tiktoken):
    if use_tiktoken:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return lambda text: len(enc.encode(text))
    return lambda text: round(len(text) / 4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir")
    parser.add_argument("--tiktoken", action="store_true")
    args = parser.parse_args()
    count = make_counter(args.tiktoken)

    total_base = total_lembas = 0
    print(f"{'eval':32} {'baseline':>8} {'lembas':>7} {'cut':>7}")
    for folder in sorted(p for p in pathlib.Path(args.results_dir).iterdir() if p.is_dir()):
        base = count((folder / "baseline.md").read_text())
        lembas = count((folder / "lembas.md").read_text())
        total_base += base
        total_lembas += lembas
        print(f"{folder.name:32} {base:8} {lembas:7} {100 * (1 - lembas / base):6.1f}%")
    print(f"{'TOTAL':32} {total_base:8} {total_lembas:7} {100 * (1 - total_lembas / total_base):6.1f}%")


if __name__ == "__main__":
    main()
