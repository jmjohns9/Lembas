#!/usr/bin/env python3
"""Claude Code hook: compress large Bash and Read results before Claude reads them.

What it does
    PostToolUse, Bash   If a command dumps a large log, JSON or CSV (a test run, a build, an API call,
                        cat of a big file), Claude sees a summary instead. Every error and stack trace
                        is kept, and the full output stays on disk. Commands that already narrow their
                        output (grep, head, sed -n, awk, a jq filter) are deliberate queries and are left
                        alone unless the result is over Claude Code's 30,000-character inline limit.
    PostToolUse, Read   Same for large .log, .json, .jsonl and .csv reads. Reads with an
                        offset or limit are left alone, because those ask for exact lines.
    PreToolUse,  Read   A Read of a data file over 256 KB would fail. The hook declines it
                        and gives Claude the summary and the path instead.

Source code, diffs and small outputs are never changed. Prefix a command with
LEMBAS_RAW=1 to get its raw output, or set LEMBAS_SQUEEZE=0 to switch the hook off.

Install: run `python3 squeeze_hook.py --print-settings` and merge the JSON it prints into
~/.claude/settings.json (or a project's .claude/settings.json).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import squeeze  # noqa: E402

READ_LIMIT = 256 * 1024          # Claude Code's Read size limit
INLINE_LIMIT = 30000             # Claude Code shows Bash output up to about this many characters inline
# A command that already narrows its output (grep, head, sed -n, a jq filter...) is a deliberate query.
# Its result is what Claude asked for, so it is only squeezed when it is too big to show anyway.
NARROWING = re.compile(r"(^|[|;&(]\s*|\s)(grep|egrep|rg|ag|head|tail|sed|awk|cut|jq|yq|sort|uniq|wc|tr|column|less|more|xargs)\b")
MAX_SCAN = 64 * 1024 * 1024      # don't load more than this from a saved output
DATA_EXTS = {".log", ".out", ".json", ".jsonl", ".ndjson", ".csv", ".tsv"}
BUDGET = int(os.environ.get("LEMBAS_SQUEEZE_BUDGET", squeeze.DEFAULT_BUDGET))
THRESHOLD = int(os.environ.get("LEMBAS_SQUEEZE_THRESHOLD", squeeze.DEFAULT_THRESHOLD))


def emit(obj):
    sys.stdout.write(json.dumps(obj))


def read_text(path, limit=MAX_SCAN):
    with open(path, "rb") as fh:
        return fh.read(limit).decode("utf-8", "replace")


def on_bash(data):
    cmd = (data.get("tool_input") or {}).get("command", "")
    if "LEMBAS_RAW=1" in cmd or "squeeze.py" in cmd:
        return
    resp = data.get("tool_response")
    if not isinstance(resp, dict) or resp.get("isImage"):
        return
    saved = resp.get("persistedOutputPath")
    if saved and os.path.exists(saved):
        stdout, original = read_text(saved), saved          # full output, not the truncated preview
    else:
        stdout, original = resp.get("stdout") or "", None
    narrowed = bool(NARROWING.search(cmd))
    threshold = squeeze.est_tokens("x" * INLINE_LIMIT) if narrowed else THRESHOLD
    new = dict(resp)
    changed = False
    view, _ = squeeze.squeeze(stdout, None, "auto", BUDGET, threshold, original)
    if view is not None:
        new["stdout"] = view
        changed = True
    stderr = resp.get("stderr") or ""
    if stderr:
        view, _ = squeeze.squeeze(stderr, None, "auto", BUDGET, threshold, None)
        if view is not None:
            new["stderr"] = view
            changed = True
    if changed:
        emit({"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": new}})


def _is_slice(tool_input):
    return bool(tool_input.get("offset") or tool_input.get("limit") or tool_input.get("pages"))


def on_read_post(data):
    ti = data.get("tool_input") or {}
    resp = data.get("tool_response")
    if _is_slice(ti) or not isinstance(resp, dict) or resp.get("type") != "text":
        return
    f = resp.get("file") or {}
    path = f.get("filePath") or ti.get("file_path", "")
    if os.path.splitext(path)[1].lower() not in DATA_EXTS:
        return
    view, _ = squeeze.squeeze(f.get("content") or "", path, "auto", BUDGET, THRESHOLD, path)
    if view is None:
        return
    new = json.loads(json.dumps(resp))
    nlines = view.count("\n") + 1
    new["file"].update(content=view, numLines=nlines, totalLines=nlines, startLine=1)
    emit({"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": new}})


def on_read_pre(data):
    ti = data.get("tool_input") or {}
    path = ti.get("file_path", "")
    if _is_slice(ti) or os.path.splitext(path)[1].lower() not in DATA_EXTS:
        return
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size <= READ_LIMIT:
        return
    view, _ = squeeze.squeeze(read_text(path), path, "auto", BUDGET, 0, path)
    if view is None:
        return
    reason = (f"This file is {size / 1_048_576:.1f} MB, over the Read tool's 256 KB limit, so the lembas "
              f"squeeze hook returned a summary instead. Use grep, sed, jq or Read with offset/limit "
              f"on {path} for exact lines.\n\n{view}")
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})


SETTINGS = {
    "hooks": {
        "PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": None}]}],
        "PostToolUse": [{"matcher": "Bash|Read", "hooks": [{"type": "command", "command": None}]}],
    }
}


def main():
    if "--print-settings" in sys.argv:
        cmd = f'python3 "{os.path.abspath(__file__)}"'
        for event in SETTINGS["hooks"].values():
            event[0]["hooks"][0]["command"] = cmd
        print(json.dumps(SETTINGS, indent=2))
        return 0
    if os.environ.get("LEMBAS_SQUEEZE", "1") == "0":
        return 0
    try:
        data = json.load(sys.stdin)
        event, tool = data.get("hook_event_name"), data.get("tool_name")
        if event == "PostToolUse" and tool == "Bash":
            on_bash(data)
        elif event == "PostToolUse" and tool == "Read":
            on_read_post(data)
        elif event == "PreToolUse" and tool == "Read":
            on_read_pre(data)
    except Exception as exc:  # a hook bug must never break the tool call
        sys.stderr.write(f"lembas squeeze hook skipped: {exc!r}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
