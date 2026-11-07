#!/usr/bin/env python3
"""Apply jmgo compatibility patches to a checked-out upstream FongMi/TV tree.

Patch format (one file per patch, e.g. P001-runtime-catalog.patch):

    # jmgo-patch v1
    # id: P001
    # why: <free text, ignored>
    # required: true|false      (optional; default false = best-effort)
    # target: <path relative to upstream root>
    @@
    <exact old text, may span multiple lines>
    --- NEW
    <exact new text, may span multiple lines>
    # target: <another path>     (a patch may touch several files)
    @@
    ...

Rules:
  * Lines beginning with "# " are metadata. "# target:" switches the file.
    "# id:" / "# required:" set patch id / required flag. Other "# " lines are
    ignored and are NEVER treated as patch content.
  * A hunk is delimited by "@@" (start of old text) ... "--- NEW" (start of new
    text) ... next "@@" / "# target:" / EOF.
  * Matching is exact substring on the old text. First occurrence is replaced.
  * required=True  -> missing match aborts (exit 1); best-effort -> skipped.
  * Result written to <upstream>/patches-applied.json for downstream audit.
"""

import argparse
import json
import sys
from pathlib import Path


def parse_patch(path: Path):
    """Return list of hunks: dict(target, old, new). Also patch id/required."""
    meta = {"id": path.stem, "required": False}
    hunks = []
    cur_target = None
    mode = None  # None | "old" | "new"
    old_lines, new_lines = [], []
    raw = path.read_text(encoding="utf-8").splitlines()

    def flush():
        nonlocal old_lines, new_lines, mode
        if mode in ("old", "new") and old_lines:
            hunks.append({
                "target": cur_target,
                "old": "\n".join(old_lines),
                "new": "\n".join(new_lines),
            })
        old_lines, new_lines = [], []
        mode = None

    for line in raw:
        if line.startswith("# target:"):
            flush()
            cur_target = line[len("# target:"):].strip()
            continue
        if line.startswith("# id:"):
            meta["id"] = line[len("# id:"):].strip()
            continue
        if line.startswith("# required:"):
            meta["required"] = line[len("# required:"):].strip().lower() == "true"
            continue
        if line.startswith("# "):  # other metadata
            continue
        if line == "@@":
            flush()
            mode = "old"
            continue
        if line == "--- NEW":
            mode = "new"
            continue
        if mode == "old":
            old_lines.append(line)
        elif mode == "new":
            new_lines.append(line)
    flush()
    return meta, hunks


def apply_hunk(upstream: Path, hunk, meta):
    if not hunk["target"]:
        return {"status": "failed", "reason": "no # target specified",
                "target": hunk.get("target")}
    f = upstream / hunk["target"]
    if not f.is_file():
        return {"status": "skipped", "reason": "target file not found",
                "target": hunk["target"]}
    text = f.read_text(encoding="utf-8")
    if hunk["old"] not in text:
        return {"status": "skipped", "reason": "old text not found (already patched or upstream changed)",
                "target": hunk["target"]}
    # guard against duplicate application
    if hunk["new"] in text.split(hunk["old"], 1)[0]:
        return {"status": "skipped", "reason": "new text already present",
                "target": hunk["target"]}
    text = text.replace(hunk["old"], hunk["new"], 1)
    f.write_text(text, encoding="utf-8")
    return {"status": "applied", "target": hunk["target"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, help="path to checked-out upstream root")
    ap.add_argument("--patches-dir", required=True, help="dir containing *.patch")
    ap.add_argument("--upstream-sha", default="", help="recorded for audit")
    args = ap.parse_args()

    upstream = Path(args.upstream).resolve()
    pdir = Path(args.patches_dir)
    patch_files = sorted(pdir.glob("*.patch"))
    if not patch_files:
        print(f"[apply_patches] no .patch files in {pdir}", file=sys.stderr)
        sys.exit(2)

    report = {"upstream_sha": args.upstream_sha, "applied": [], "skipped": [], "failed": []}
    required_failed = False

    for pf in patch_files:
        meta, hunks = parse_patch(pf)
        print(f"[apply_patches] {meta['id']} ({'REQUIRED' if meta['required'] else 'best-effort'}) "
              f"-> {len(hunks)} hunk(s)")
        for h in hunks:
            res = apply_hunk(upstream, h, meta)
            entry = {"id": meta["id"], **res}
            if res["status"] == "applied":
                report["applied"].append(entry)
                print(f"    applied   {h['target']}")
            elif res["status"] == "skipped":
                report["skipped"].append(entry)
                print(f"    skipped  {h.get('target')}: {res['reason']}")
            else:  # failed
                report["failed"].append(entry)
                print(f"    FAILED   {h.get('target')}: {res['reason']}", file=sys.stderr)
                if meta["required"]:
                    required_failed = True

    out = upstream / "patches-applied.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[apply_patches] wrote {out}")
    print(f"[apply_patches] applied={len(report['applied'])} "
          f"skipped={len(report['skipped'])} failed={len(report['failed'])}")

    if required_failed:
        print("[apply_patches] a REQUIRED patch failed -> abort", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
