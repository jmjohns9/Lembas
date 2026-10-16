#!/usr/bin/env python3
"""squeeze.py: shrink large logs, JSON and CSV before a language model reads them.

Usage:
    python3 squeeze.py FILE                 # summarize a file (original stays where it is)
    some_command 2>&1 | python3 squeeze.py  # summarize piped output (original saved to a cache file)

Options:
    --type auto|log|json|jsonl|csv|text   force a format (default: detect)
    --budget N      target size of the summary in tokens (default 1500)
    --threshold N   inputs under this many tokens pass through unchanged (default 2000)
    --stats         print size before and after to stderr

Guarantees:
    * Every error line, warning and stack trace is kept (repeats are counted, not dropped).
    * Line numbers (L123) refer to the original, so you can grep or sed it for anything not shown.
    * The original is never modified. Piped input is saved to $LEMBAS_SQUEEZE_DIR (default
      $TMPDIR/lembas-squeeze, readable by you only) and the summary prints its path.
    * Source code, diffs and plain prose pass through unchanged in auto mode.
    * If squeezing fails or saves less than 30%, the input is printed unchanged.

Standard library only. Python 3.8+.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import statistics
import sys
import tempfile
from collections import Counter

VERSION = "1.0.0"
DEFAULT_THRESHOLD = 2000
DEFAULT_BUDGET = 1500
MIN_SAVING = 0.30
MAX_LINE = 300

CODE_EXTS = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".scala",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".m", ".sh", ".bash", ".zsh",
    ".sql", ".html", ".css", ".scss", ".vue", ".svelte", ".lua", ".pl", ".r", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".xml", ".md", ".rst", ".tex", ".dockerfile", ".tf", ".gradle",
}
DATA_TYPES = {"log", "json", "jsonl", "csv"}


def est_tokens(text):
    # Logs, JSON and CSV tokenize at roughly 2.5 to 3.5 characters per token, so 3 is a safe estimate.
    return (len(text) + 2) // 3


# --------------------------------------------------------------------------- cleaning

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def clean(text):
    """Remove terminal color codes and progress-bar redraws. Meaning is unchanged."""
    text = ANSI.sub("", text)
    if "\r" in text:
        out = []
        for line in text.split("\n"):
            line = line.rstrip("\r")
            if "\r" in line:
                line = line.rsplit("\r", 1)[-1]
            out.append(line)
        text = "\n".join(out)
    return text


def clip(line, limit=MAX_LINE):
    if len(line) <= limit:
        return line
    return f"{line[:limit]}…[+{len(line) - limit} chars]"


# --------------------------------------------------------------------------- detection

TS_START = re.compile(
    r"^\s*[\[(]?(?:\d{4}-\d{2}-\d{2}[T ]\d{1,2}:\d{2}|\d{2}:\d{2}:\d{2}|"
    r"[A-Z][a-z]{2}\s+\d{1,2}\s\d{2}:\d{2}:\d{2}|\d{1,2}/[A-Za-z]{3}/\d{4}|1\d{9,12}\b)"
)
LEVEL = re.compile(r"\b(TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|ERR|FATAL|CRITICAL|SEVERE|PASSED|FAILED)\b")
CODE_LINE = re.compile(
    r"^\s*(def |class |import |from \S+ import|function\b|const |let |var |return\b|if\s*\(|for\s*\(|"
    r"#include|package |public |private |func |fn |use |pub |@\w+|\}|\{$)|[;{]\s*$"
)


def _is_json_obj(line):
    line = line.strip()
    if not (line.startswith("{") and line.endswith("}")):
        return False
    try:
        json.loads(line)
        return True
    except ValueError:
        return False


def _csv_shape(lines):
    """Return a csv dialect if the lines look like a delimited table, else None."""
    sample = [l for l in lines[:60] if l.strip()]
    if len(sample) < 5:
        return None
    for delim in (",", "\t", ";", "|"):
        try:
            rows = list(csv.reader(sample, delimiter=delim))
        except csv.Error:
            continue
        widths = Counter(len(r) for r in rows)
        width, hits = widths.most_common(1)[0]
        if width >= 2 and hits >= 0.9 * len(rows):
            # Reject prose and logs that happen to contain the delimiter.
            if delim == "," and sum(bool(TS_START.match(l)) for l in sample) > len(sample) / 2:
                return None
            return delim
    return None


def detect(text, name=None):
    ext = os.path.splitext(name or "")[1].lower()
    if ext == ".json":
        return "json"
    if ext in (".jsonl", ".ndjson"):
        return "jsonl"
    if ext in (".csv", ".tsv"):
        return "csv"
    if ext in CODE_EXTS:
        return "code"
    stripped = text.lstrip()
    if stripped[:1] in "{[":
        try:
            json.loads(stripped)
            return "json"
        except ValueError:
            pass
    lines = text.split("\n")
    head = [l for l in lines[:50] if l.strip()]
    if not head:
        return "text"
    if sum(_is_json_obj(l) for l in head) >= 0.9 * len(head):
        return "jsonl"
    if any(l.startswith("diff --git") or l.startswith("@@ ") for l in head[:20]):
        return "diff"
    if _csv_shape(lines):
        return "csv"
    sample = lines[:400]
    nonblank = [l for l in sample if l.strip()] or [""]
    stamped = sum(bool(TS_START.match(l) or LEVEL.search(l)) for l in nonblank) / len(nonblank)
    codey = sum(bool(CODE_LINE.search(l)) for l in nonblank) / len(nonblank)
    if codey >= 0.3 and stamped < 0.2:
        return "code"
    if stamped >= 0.2:
        return "log"
    firsts = Counter(l.split(None, 1)[0] for l in nonblank if l.split())
    if len(nonblank) >= 50 and firsts and firsts.most_common(1)[0][1] >= 0.5 * len(nonblank):
        return "log"
    if len(lines) >= 100:
        templates = {template(l) for l in lines[:2000]}
        if len(templates) <= 0.5 * min(len(lines), 2000):
            return "log"
    return "text"


# --------------------------------------------------------------------------- logs

# Error words must stand alone: "http-errors", "/api/error" and "app.error" are names, not errors.
_ALONE_L = r"(?<![-/@.\w])"
_ALONE_R = r"(?![-/\w]|\.\w)"
ERR = re.compile(
    r"(?i)" + _ALONE_L + r"(error|errors|err|fatal|critical|crit|panic|panicked|exception|traceback|failed|failure|"
    r"denied|refused|segfault|segmentation fault|aborted|killed|oom|out of memory|unhandled|uncaught|"
    r"timed out|timeout)" + _ALONE_R +
    r"|(?-i:[A-Za-z]+(?:Error|Exception))\b|\"\s5\d\d\s|\bHTTP/\d(?:\.\d)?\"?\s5\d\d\b"
)
WARN = re.compile(r"(?i)" + _ALONE_L + r"(warn|warning|warnings|deprecated|deprecation|retry|retrying)" + _ALONE_R + r"|\"\s4\d\d\s")
NOT_ERR = re.compile(
    r"(?i)\b(0|no) (errors?|failures?|failed)\b|\berrors?\s*[=:]\s*0\b|\bfailed\s*[=:]\s*0\b|\bwithout errors?\b"
)
CONT = re.compile(
    r"^(\s+at\s|\s+File \"|\s+\.\.\.\s*\d+ more|Caused by:|Traceback \(|\s{2,}\S|\t\S|"
    r"[A-Za-z_][\w.]*(Error|Exception)(:|$)|During handling|The above exception)"
)
NORM = [
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<ts>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<id>"),
    (re.compile(r"\b[a-z][\w+.-]*://\S+", re.I), "<url>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ip>"),
]
_WORD = re.compile(r"^[A-Za-z_'\"()\[\]<>]+[:,;.]?$")
_VAR = re.compile(r"[\d@%=]")  # tokens with digits, @, % or = vary between lines; routes like /api/cart don't


def template(line):
    """Reduce a log line to its pattern: variable tokens (numbers, paths, ids, k=v values) become <*>."""
    for rx, rep in NORM:
        line = rx.sub(rep, line)
    out = []
    for tok in line.split():
        if _WORD.match(tok) or tok in ("<ts>", "<id>", "<url>", "<ip>") or not _VAR.search(tok):
            out.append(tok)
        elif "=" in tok:
            out.append(tok.split("=", 1)[0] + "=<*>")
        elif out and out[-1] == "<*>":
            continue
        else:
            out.append("<*>")
    return " ".join(out)[:160]


PYTEST_E = re.compile(r"^E\s{2,}\S")


def _error_key(line):
    """Grouping key for error lines: keep file paths and words, vary only numbers and ids."""
    for rx, rep in NORM:
        line = rx.sub(rep, line)
    return re.sub(r"\d+", "<n>", line).strip()[:200]


def _severity(line):
    if PYTEST_E.match(line):
        return 2
    if ERR.search(line) and not NOT_ERR.search(line):
        return 2
    if WARN.search(line):
        return 1
    return 0


def squeeze_log(text, budget):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    n = len(lines)
    sev = [_severity(l) for l in lines]
    tpl = [template(l) for l in lines]
    tcount = Counter(tpl)

    # Group error events (an error line plus its stack trace) and warnings by template.
    events = {}   # template -> dict(first=(start, end), count, last, sev)
    order = []
    event_lines = set()
    i = 0
    while i < n:
        if sev[i]:
            start, j = i, i + 1
            if sev[i] == 2:
                while j < n and j - start < 60 and CONT.match(lines[j]):
                    j += 1
            event_lines.update(range(start, j))
            key = (sev[i], _error_key(lines[i]) if sev[i] == 2 else template(lines[i]))
            ev = events.get(key)
            if ev is None:
                # Keep up to 3 lines before the first occurrence: they usually show what led to it.
                pre = start
                while (pre > 0 and start - pre < 3 and lines[pre - 1].strip() and not sev[pre - 1]
                       and tcount[tpl[pre - 1]] <= 20):
                    pre -= 1
                events[key] = {"first": (start, j - 1), "pre": pre, "count": 1, "last": start, "sev": sev[i]}
                order.append(key)
            else:
                ev["count"] += 1
                ev["last"] = start
            i = j
        else:
            i += 1

    def render(head_n, tail_n, max_err, max_warn, trace_cap, top_k):
        shown = set()
        notes = {}
        for k in range(min(head_n, n)):
            shown.add(k)
        for k in range(max(0, n - tail_n), n):
            shown.add(k)
        errs = [k for k in order if k[0] == 2]
        warns = [k for k in order if k[0] == 1]
        extra = []
        for key in errs[:max_err] + warns[:max_warn]:
            ev = events[key]
            s, e = ev["first"]
            if key[0] == 2:
                shown.update(range(ev["pre"], s))
            span = list(range(s, e + 1))
            if len(span) > trace_cap:
                keep_head = trace_cap // 2
                span = span[:keep_head] + span[-(trace_cap - keep_head):]
                notes[span[keep_head - 1]] = f"      …[{e - s + 1 - trace_cap} trace lines omitted]"
            shown.update(span)
            if ev["count"] > 1:
                notes[span[-1]] = (notes.get(span[-1], "") + "\n" if span[-1] in notes else "") + \
                    f"      [this {'error' if key[0] == 2 else 'warning'} repeats {ev['count']}× in total, last at L{ev['last'] + 1}]"
        hidden_err = len(errs) - min(len(errs), max_err)
        hidden_warn = len(warns) - min(len(warns), max_warn)
        if hidden_err:
            extra.append(f"[{hidden_err} more distinct error messages not shown: grep -n -i -E 'error|exception|fail' the original]")
        if hidden_warn:
            extra.append(f"[{hidden_warn} more distinct warnings not shown]")

        out = []
        prev = -1
        for k in sorted(shown):
            if k > prev + 1:
                out.append(f"  … L{prev + 2}–L{k}: {k - prev - 1} lines collapsed (see summary below)")
            out.append(f"L{k + 1} {clip(lines[k])}")
            if k in notes:
                out.append(notes[k])
            prev = k
        if prev < n - 1:
            out.append(f"  … L{prev + 2}–L{n}: {n - prev - 1} lines collapsed")
        out.extend(extra)

        rest = Counter()
        first_at = {}
        for k in range(n):
            if k not in shown and k not in event_lines and lines[k].strip():
                t = tpl[k]
                rest[t] += 1
                first_at.setdefault(t, k)
        if rest:
            out.append(f"Collapsed lines: {sum(rest.values())} lines in {len(rest)} patterns. Most common (count × first example):")
            for t, c in rest.most_common(top_k):
                out.append(f"  {c}× L{first_at[t] + 1} {clip(lines[first_at[t]], 200)}")
            if len(rest) > top_k:
                out.append(f"  … {len(rest) - top_k} rarer patterns")
        return "\n".join(out)

    levels = [
        (5, 15, 40, 15, 30, 12),
        (4, 12, 30, 10, 24, 10),
        (3, 10, 25, 6, 18, 8),
        (3, 8, 20, 4, 14, 6),
        (2, 5, 15, 3, 10, 4),
    ]
    body = ""
    for lv in levels:
        body = render(*lv)
        if est_tokens(body) <= budget:
            break
    n_err = sum(e["count"] for k, e in events.items() if k[0] == 2)
    n_warn = sum(e["count"] for k, e in events.items() if k[0] == 1)
    kinds = sum(1 for k in events if k[0] == 2)
    facts = f"{n:,} lines, {n_err:,} error lines ({kinds} distinct), {n_warn:,} warnings"
    return body, facts


# --------------------------------------------------------------------------- JSON

ERR_KEYS = {"error", "errors", "err", "exception", "failure", "fault", "stacktrace", "stack_trace"}
STATUS_KEYS = re.compile(r"(?i)^(status|state|result|level|severity|conclusion|outcome|health)$")
CODE_KEYS = re.compile(r"(?i)^(status_?code|http_?status|code|status)$")
BAD_VALUE = re.compile(r"(?i)\b(error|fail(ed|ure)?|fatal|critical|denied|timeout|timed.out|cancel(l)?ed|unhealthy|down)\b")


def _scalar(v):
    return v is None or isinstance(v, (str, int, float, bool))


def _fmt(v, str_len):
    if isinstance(v, str):
        s = json.dumps(v if len(v) <= str_len else v[:str_len], ensure_ascii=False)
        return s if len(v) <= str_len else f"{s}…(+{len(v) - str_len} chars)"
    return json.dumps(v)


def _flatten(obj, prefix="", depth=0, out=None):
    out = {} if out is None else out
    for k, v in obj.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and depth < 2:
            _flatten(v, key + ".", depth + 1, out)
        else:
            out[key] = v
    return out


def _is_bad(item):
    flat = _flatten(item) if isinstance(item, dict) else {}
    for k, v in flat.items():
        leaf = k.rsplit(".", 1)[-1]
        if leaf.lower() in ERR_KEYS and v not in (None, "", [], {}, False, 0):
            return True
        if STATUS_KEYS.match(leaf) and isinstance(v, str) and BAD_VALUE.search(v):
            return True
        if CODE_KEYS.match(leaf) and isinstance(v, int) and not isinstance(v, bool) and 400 <= v <= 599:
            return True
    return False


def _bad_repr(item, limit):
    """One line per failing item with the identifying and error fields first, so clipping never hides them."""
    if not isinstance(item, dict):
        return clip(json.dumps(item, ensure_ascii=False), limit)
    flat = _flatten(item)

    def rank(k):
        parts = k.lower().split(".")
        if parts[-1] in ("id", "name", "key", "uuid") and len(parts) == 1:
            return 0
        if parts[0] in ERR_KEYS or parts[-1] in ERR_KEYS or STATUS_KEYS.match(parts[-1]) or CODE_KEYS.match(parts[-1]):
            return 1
        return 2
    keys = sorted(flat, key=rank)
    text = "; ".join(f"{k}={json.dumps(flat[k], ensure_ascii=False)}" for k in keys)
    return clip(text, limit)


def _type(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "num"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "array"
    return "object"


def _num(x):
    return f"{x:,.4g}" if isinstance(x, float) else f"{x:,}"


def _field_summary(values, total, str_len):
    present = len(values)
    types = Counter(_type(v) for v in values)
    nulls = types.pop("null", 0)
    parts = ["/".join(t for t, _ in types.most_common()) or "null", f"{present}/{total}"]
    if nulls:
        parts.append(f"{nulls} null")
    vals = [v for v in values if _scalar(v) and v is not None]
    if vals:
        hashable = [v if not isinstance(v, float) else round(v, 6) for v in vals]
        distinct = Counter(hashable)
        nums = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(distinct) <= 8:
            parts.append(", ".join(f"{_fmt(v, 40)}×{c}" for v, c in distinct.most_common()))
        elif nums and len(nums) == len(vals):
            uniq = " (unique)" if len(distinct) == len(vals) else ""
            parts.append(f"{_num(min(nums))}…{_num(max(nums))}{uniq}")
        else:
            uniq = "unique" if len(distinct) == len(vals) else f"{len(distinct):,} distinct"
            ex = ", ".join(_fmt(v, str_len) for v, _ in distinct.most_common(2))
            parts.append(f"{uniq}, e.g. {ex}")
    lists = [v for v in values if isinstance(v, list)]
    if lists:
        lens = [len(v) for v in lists]
        inner = Counter(_type(x) for v in lists for x in v[:50])
        parts.append(f"len {min(lens)}–{max(lens)}" + (f" of {inner.most_common(1)[0][0]}" if inner else ""))
    return ", ".join(parts)


def _render_json(v, path, depth, L, out, ind):
    pad = "  " * ind
    if isinstance(v, dict):
        if depth >= L["depth"]:
            out.append(f"{pad}{{{len(v)} keys: {', '.join(list(v)[:10])}}}")
            return
        keys = list(v)
        if len(keys) > L["keys"]:
            tail_keys = keys[-3:]
            hidden = len(keys) - L["keys"]
            keys_shown = keys[: L["keys"] - 3]
        else:
            tail_keys, hidden, keys_shown = [], 0, keys
        for idx, k in enumerate(keys_shown + tail_keys):
            if hidden and idx == len(keys_shown):
                out.append(f"{pad}… {hidden} keys not shown (first: {keys[len(keys_shown)]}, last: {keys[-4]}); last 3 keys:")
            x = v[k]
            sub = f"{path}.{k}" if re.match(r"^[A-Za-z_]\w*$", str(k)) else f"{path}[{json.dumps(k)}]"
            if _scalar(x):
                out.append(f"{pad}{k}: {_fmt(x, L['str'])}")
            elif isinstance(x, dict) and not x:
                out.append(f"{pad}{k}: {{}}")
            elif isinstance(x, dict):
                out.append(f"{pad}{k}:")
                _render_json(x, sub, depth + 1, L, out, ind + 1)
            else:
                _render_array(x, sub, depth + 1, L, out, ind, label=k)
    elif isinstance(v, list):
        _render_array(v, path, depth, L, out, ind, label=None)
    else:
        out.append(f"{pad}{_fmt(v, L['str'])}")


def _render_array(arr, path, depth, L, out, ind, label):
    pad = "  " * ind
    name = f"{label}: " if label is not None else ""
    n = len(arr)
    if n == 0:
        out.append(f"{pad}{name}[]")
        return
    if all(_scalar(x) for x in arr):
        if n <= 8:
            out.append(f"{pad}{name}[{', '.join(_fmt(x, L['str']) for x in arr)}]")
        else:
            out.append(f"{pad}{name}array[{n}] at {path or '.'}: {_field_summary(arr, n, L['str'])}")
        return
    dicts = [x for x in arr if isinstance(x, dict)]
    out.append(f"{pad}{name}array[{n}] of {'objects' if len(dicts) == n else 'mixed'} at {path or '.'}")
    pad2 = pad + "  "
    if dicts and depth < L["depth"] + 1:
        flats = [_flatten(d) for d in dicts]
        fields = {}
        for f in flats:
            for k in f:
                fields.setdefault(k, None)
        keys = list(fields)
        out.append(f"{pad2}fields ({len(keys)}):")
        shown = 0
        for k in keys:
            vals = [f[k] for f in flats if k in f]
            if len(vals) < max(1, 0.05 * len(flats)) and len(flats) >= 20:
                continue  # rare fields are listed separately
            if shown >= L["fields"]:
                break
            out.append(f"{pad2}  {k}: {_field_summary(vals, len(flats), L['str'])}")
            shown += 1
        common = [k for k in keys if not (len(flats) >= 20 and sum(k in f for f in flats) < max(1, 0.05 * len(flats)))]
        if len(common) > shown:
            out.append(f"{pad2}  … +{len(common) - shown} more fields: {', '.join(common[shown:shown + 12])}")
        rare = [k for k in keys if k not in common]
        if rare:
            desc = []
            for k in rare[:6]:
                idx = [i for i, f in enumerate(flats) if k in f][:4]
                desc.append(f"{k} (in {sum(k in f for f in flats)} items, e.g. [{', '.join(map(str, idx))}])")
            out.append(f"{pad2}rare fields: {'; '.join(desc)}")
    if L["samples"]:
        out.append(f"{pad2}[0]:")
        _render_json(arr[0], f"{path}[0]", depth + 1, L, out, ind + 2)
    bad = [i for i, x in enumerate(arr) if _is_bad(x)]
    if bad:
        out.append(f"{pad2}items that look like errors or failures: {len(bad)} (indexes {', '.join(map(str, bad[:12]))}{'…' if len(bad) > 12 else ''})")
        for i in bad[: L["bad"]]:
            out.append(f"{pad2}  [{i}] {_bad_repr(arr[i], L['line'])}")
    if n > 1 and L["samples"]:
        out.append(f"{pad2}[{n - 1}] {clip(json.dumps(arr[-1], ensure_ascii=False), L['line'])}")


def squeeze_json(obj, budget, kind="json"):
    levels = [
        dict(depth=6, keys=40, fields=40, str=120, samples=1, bad=8, line=400),
        dict(depth=5, keys=25, fields=25, str=80, samples=1, bad=5, line=300),
        dict(depth=4, keys=15, fields=18, str=60, samples=1, bad=3, line=220),
        dict(depth=3, keys=10, fields=12, str=40, samples=0, bad=3, line=160),
        dict(depth=2, keys=8, fields=8, str=30, samples=0, bad=2, line=120),
    ]
    body = ""
    for L in levels:
        out = []
        _render_json(obj, "", 0, L, out, 0)
        body = "\n".join(out)
        if est_tokens(body) <= budget:
            break
    if isinstance(obj, list):
        facts = f"top level: array of {len(obj):,}"
    elif isinstance(obj, dict):
        facts = f"top level: object with {len(obj):,} keys"
    else:
        facts = "scalar"
    return body, facts


# --------------------------------------------------------------------------- CSV

NULLS = {"", "na", "n/a", "null", "none", "nan", "nil", "-", "#n/a"}
INT_RE = re.compile(r"^[+-]?\d{1,18}$")
FLOAT_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
DATE_RE = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")
BOOL = {"true", "false", "yes", "no", "t", "f", "y", "n"}


def _num_value(s):
    s = s.strip().replace(",", "") if s.count(",") and re.match(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$", s.strip()) else s.strip()
    s = s.lstrip("$€£")
    return float(s) if FLOAT_RE.match(s) else None


def _numfmt(x):
    if x == int(x) and abs(x) < 1e15:
        return f"{x:,.0f}"
    return f"{x:,.2f}" if abs(x) >= 100 else f"{x:,.6g}"


def _profile_column(vals, line_nos, str_len):
    total = len(vals)
    present = [(v.strip(), ln) for v, ln in zip(vals, line_nos) if v.strip().lower() not in NULLS]
    nulls = total - len(present)
    p = [v for v, _ in present]
    if not p:
        return "empty", nulls, "all null", []
    if all(INT_RE.match(v) for v in p):
        kind = "int"
    elif all(_num_value(v) is not None for v in p):
        kind = "float"
    elif all(DATE_RE.match(v) for v in p):
        kind = "date"
    elif all(v.lower() in BOOL for v in p):
        kind = "bool"
    else:
        kind = "text"
    distinct = Counter(p)
    flags = []
    if kind in ("int", "float"):
        nums = [_num_value(v) for v in p]
        lo, hi = min(nums), max(nums)
        fmt = _numfmt
        unique = len(distinct) == len(p)
        if unique and kind == "int" and len(p) > 20:
            summary = f"{fmt(lo)}…{fmt(hi)}, unique (likely an ID)"
        else:
            summary = (f"min {fmt(lo)}, max {fmt(hi)}, mean {fmt(statistics.fmean(nums))}, "
                       f"median {fmt(statistics.median(nums))}, sum {fmt(sum(nums))}")
            if len(distinct) <= 6:
                summary = ", ".join(f"{v}×{c}" for v, c in distinct.most_common()) + "; " + summary
            # Flag a value only when it is far from everything else (a shifted decimal, a sentinel
            # like -1 or 999999). Skewed but real distributions don't trigger this.
            ranked = sorted(zip(nums, (ln for _, ln in present)), key=lambda t: t[0])
            if len(ranked) >= 10:
                (top, top_ln), (nxt, _) = ranked[-1], ranked[-2]
                if nxt > 0 and top >= 5 * nxt:
                    flags.append(f"max {fmt(top)} at L{top_ln} is {top / nxt:,.1f}× the next largest ({fmt(nxt)})")
                (bot, bot_ln), (nxt_lo, _) = ranked[0], ranked[1]
                if bot < 0 <= nxt_lo:
                    flags.append(f"min {fmt(bot)} at L{bot_ln} is the only negative value")
    elif kind == "date":
        summary = f"{min(p)} … {max(p)}, {len(distinct):,} distinct"
    elif len(distinct) <= 12:
        summary = ", ".join(f"{_fmt(v, 30)}×{c}" for v, c in distinct.most_common())
    else:
        top = [(v, c) for v, c in distinct.most_common(4) if c > 1]
        uniq = "unique" if len(distinct) == len(p) else f"{len(distinct):,} distinct"
        lens = [len(v) for v in p]
        summary = uniq + (f", length {min(lens)}–{max(lens)}" if min(lens) != max(lens) else "")
        if top:
            summary += "; top " + ", ".join(f"{_fmt(v, str_len)}×{c}" for v, c in top)
        else:
            summary += f"; e.g. {_fmt(p[0], str_len)}"
    return kind, nulls, summary, flags


def squeeze_csv(text, budget):
    lines = text.split("\n")
    delim = _csv_shape(lines) or ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows, line_nos = [], []
    for row in reader:
        if row:
            rows.append(row)
            line_nos.append(reader.line_num)
    if len(rows) < 2:
        raise ValueError("not enough rows")
    try:
        has_header = csv.Sniffer().has_header("\n".join(lines[:20]))
    except csv.Error:
        has_header = True
    first = rows[0]
    if not has_header and all(_num_value(c) is None for c in first):
        has_header = True
    header = first if has_header else [f"col{i + 1}" for i in range(len(first))]
    data, data_ln = (rows[1:], line_nos[1:]) if has_header else (rows, line_nos)
    ncol = len(header)
    ragged = [(ln, len(r)) for r, ln in zip(data, data_ln) if len(r) != ncol]

    profiles = []
    for c, name in enumerate(header):
        vals = [r[c] if c < len(r) else "" for r in data]
        profiles.append((name,) + _profile_column(vals, data_ln, 40))

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, lineterminator="\n")

    def row_text(r, ln):
        buf.seek(0)
        buf.truncate()
        w.writerow(r)
        return f"L{ln} {clip(buf.getvalue().rstrip(), 400)}"

    def render(head_rows, tail_rows, max_cols):
        out = [f"columns ({ncol}), {len(data):,} data rows" + (f", delimiter {delim!r}" if delim != "," else "") + ":"]
        for name, kind, nulls, summary, flags in profiles[:max_cols]:
            null_txt = f", {nulls:,} null" if nulls else ""
            out.append(f"  {clip(name, 60)} ({kind}{null_txt}): {summary}")
            for f in flags:
                out.append(f"    ! {f}")
        if ncol > max_cols:
            out.append(f"  … +{ncol - max_cols} more columns: {', '.join(header[max_cols:max_cols + 20])}")
        if ragged:
            ex = ", ".join(f"L{ln} has {k} fields" for ln, k in ragged[:5])
            out.append(f"! {len(ragged)} rows have the wrong number of fields (expected {ncol}): {ex}")
        out.append("first rows:")
        if has_header:
            out.append(row_text(rows[0], line_nos[0]))
        for r, ln in list(zip(data, data_ln))[:head_rows]:
            out.append(row_text(r, ln))
        if len(data) > head_rows + tail_rows:
            out.append(f"  … {len(data) - head_rows - tail_rows:,} rows not shown")
        if len(data) > head_rows:
            for r, ln in list(zip(data, data_ln))[-min(tail_rows, len(data) - head_rows):]:
                out.append(row_text(r, ln))
        return "\n".join(out)

    body = ""
    for lv in [(5, 2, 60), (3, 2, 40), (2, 1, 25), (1, 1, 15)]:
        body = render(*lv)
        if est_tokens(body) <= budget:
            break
    return body, f"{len(data):,} rows × {ncol} columns"


# --------------------------------------------------------------------------- generic text

def squeeze_text(text, budget):
    lines = text.split("\n")
    n = len(lines)
    head_n = max(20, budget // 20)
    tail_n = max(20, budget // 20)
    while head_n > 5 and est_tokens("\n".join(lines[:head_n] + lines[-tail_n:])) > budget:
        head_n, tail_n = int(head_n * 0.7), int(tail_n * 0.7)
    out = [f"L{k + 1} {clip(lines[k])}" for k in range(min(head_n, n))]
    if n > head_n + tail_n:
        out.append(f"  … L{head_n + 1}–L{n - tail_n}: {n - head_n - tail_n:,} lines not shown")
    out += [f"L{k + 1} {clip(lines[k])}" for k in range(max(head_n, n - tail_n), n)]
    return "\n".join(out), f"{n:,} lines, head and tail only"


# --------------------------------------------------------------------------- driver

HINTS = {
    "log": "grep -n or sed -n 'A,Bp' the original for any line range",
    "json": "query the original with jq for exact values",
    "jsonl": "query the original with jq for exact values",
    "csv": "compute exact sums, counts and filters on the original (pandas, csvkit, awk)",
    "text": "read the original with an offset for the missing lines",
}


def save_original(text, kind, cache_dir=None):
    cache_dir = cache_dir or os.environ.get("LEMBAS_SQUEEZE_DIR") or os.path.join(tempfile.gettempdir(), "lembas-squeeze")
    # Command output can contain secrets, so the cache is readable by the current user only.
    os.makedirs(cache_dir, mode=0o700, exist_ok=True)
    ext = {"log": ".log", "json": ".json", "jsonl": ".jsonl", "csv": ".csv"}.get(kind, ".txt")
    path = os.path.join(cache_dir, hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:12] + ext)
    if not os.path.exists(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
    return path


def squeeze(text, name=None, kind="auto", budget=DEFAULT_BUDGET, threshold=DEFAULT_THRESHOLD,
            original_path=None, hard_cap=40000):
    """Return (view, info). view is None when the input should pass through unchanged.

    original_path: where the full text can be found. If None, the text is saved to the cache.
    hard_cap: in auto mode, code, diffs and prose pass through unless larger than this many tokens.
    """
    text = clean(text)
    before = est_tokens(text)
    info = {"kind": kind, "before": before, "after": before}
    if before <= threshold:
        return None, info
    if kind == "auto":
        kind = detect(text, name)
        info["kind"] = kind
        if kind not in DATA_TYPES and before <= hard_cap:
            return None, info
    if kind in ("code", "diff"):
        kind = "text"
    try:
        if kind == "json":
            body, facts = squeeze_json(json.loads(text), budget, "json")
        elif kind == "jsonl":
            recs = []
            for l in text.split("\n"):
                l = l.strip()
                if l:
                    try:
                        recs.append(json.loads(l))
                    except ValueError:
                        recs.append({"_unparsed_line": l[:200]})
            body, facts = squeeze_json(recs, budget, "jsonl")
        elif kind == "csv":
            body, facts = squeeze_csv(text, budget)
        elif kind == "log":
            body, facts = squeeze_log(text, budget)
        else:
            body, facts = squeeze_text(text, budget)
    except Exception as exc:  # never let a parser bug hide the output
        info["error"] = repr(exc)
        try:
            body, facts = squeeze_text(text, budget)
            kind = "text"
        except Exception:
            return None, info
    path = original_path or save_original(text, kind)
    header = (f"[lembas squeeze: {kind}, {facts}. ~{before:,} tokens shown as a summary. "
              f"Full original: {path} ; {HINTS.get(kind, HINTS['text'])}. Lines marked L123 are original line numbers.]")
    view = header + "\n" + body
    after = est_tokens(view)
    info.update(kind=kind, after=after, path=path)
    if after > before * (1 - MIN_SAVING):
        return None, info
    return view, info


def main(argv=None):
    ap = argparse.ArgumentParser(description="Shrink large logs, JSON and CSV before an LLM reads them.")
    ap.add_argument("file", nargs="?", default="-")
    ap.add_argument("--type", default="auto", choices=["auto", "log", "json", "jsonl", "csv", "text"])
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    if args.file == "-":
        raw = sys.stdin.buffer.read()
        name, original = None, None
    else:
        with open(args.file, "rb") as fh:
            raw = fh.read()
        name, original = args.file, os.path.abspath(args.file)
    text = raw.decode("utf-8", "replace")
    # A forced type means the caller asked for a summary, so skip the code and prose guard.
    hard_cap = 0 if args.type != "auto" else 40000
    view, info = squeeze(text, name, args.type, args.budget, args.threshold, original, hard_cap)
    out = view if view is not None else clean(text)
    sys.stdout.write(out if out.endswith("\n") else out + "\n")
    if args.stats:
        pct = 100 * (1 - info["after"] / info["before"]) if info["before"] else 0
        sys.stderr.write(f"squeeze: {info['kind']}, ~{info['before']:,} → ~{info['after']:,} tokens ({pct:.0f}% smaller)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
