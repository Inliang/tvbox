#!/usr/bin/env python3
# Migrate tvbox releases to the YYYYMMDDXXX tag scheme.
#   - Deletes the stray empty "20261108001" release first (it was incorrectly marked Latest).
#   - Recreates each release under its new tag (downloads + re-uploads assets).
#   - Idempotent: skips already-migrated pairs; repairs broken new tags.
# Run:  DRY_RUN=1 python3 scripts/rename_releases.py   (preview, no writes)
#       DRY_RUN=0 python3 scripts/rename_releases.py   (execute)
import json, os, sys, re, shutil, subprocess, urllib.request, urllib.error, urllib.parse, time

REPO = "Inliang/tvbox"
API = f"https://api.github.com/repos/{REPO}"
UPLOAD = f"https://uploads.github.com/repos/{REPO}"
CACHE = "E:/relmig_cache"
DRY = os.environ.get("DRY_RUN", "1") == "1"

# Verified mapping: old_tag -> new_tag (date + per-day sequence)
MAPPING = [
    ("jmgo-42468716759",          "20261108001"),
    ("jmgo-42490712513",          "20261108002"),
    ("jmgo-resigned-43340236494", "20261113001"),
    ("jmgo-ui-43364280836",       "20261113002"),
    ("jmgo-43364856594",          "20261113003"),
    ("jmgo-ui-43368140479",       "20261113004"),
    ("jmgo-ui-2026-11-13",        "20261113005"),
    ("jmgo-ui-2026-11-13-2",      "20261113006"),  # newest -> should become Latest
]
# The corrupt artifact from a previous failed run.
STRAY_TAG = "20261108001"
LATEST_NEW = "20261113006"


def token():
    out = subprocess.run(["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n", capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("no token")


TOKEN = token()
HDR = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json", "User-Agent": "rename"}


def api(method, path, data=None):
    url = API + path
    body = None
    headers = dict(HDR)
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    # POST is not retried (avoid accidental double-create); others retry on hiccups.
    attempts = 1 if method == "POST" else 5
    last = None
    for i in range(attempts):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as r:
                txt = r.read().decode("utf-8", "replace")
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            if e.code == 404 and method == "DELETE":
                return {}  # already gone
            if e.code in (500, 502, 503, 504) and i < attempts - 1:
                last = e
                time.sleep(3 + i * 2)
                continue
            print("  HTTP", e.code, e.read().decode("utf-8", "replace")[:400])
            raise
        except Exception as e:
            last = e
            print(f"  api {method} attempt {i+1}/{attempts} error: {e}")
            if i < attempts - 1:
                time.sleep(3 + i * 2)
                continue
            raise
    raise last


def api_upload(path, binary, ctype, name, tries=6):
    url = UPLOAD + path
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=binary,
                headers={**HDR, "Content-Type": ctype}, method="POST")
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            print(f"    upload attempt {i+1}/{tries} failed: {e}")
            if i < tries - 1:
                time.sleep(3 + i * 2)
    raise last


def download(url, dest, expect, tries=12):
    # Prefer curl with resume (-C -) + retries; far more robust over flaky proxies.
    for i in range(tries):
        rc = subprocess.run(
            ["curl", "-L", "-C", "-", "--retry", "6", "--retry-all-errors",
             "--retry-delay", "2", "--connect-timeout", "30", "-o", dest, url],
            capture_output=True,
        ).returncode
        if rc == 0 and os.path.exists(dest) and os.path.getsize(dest) == expect:
            return True
        cur = os.path.getsize(dest) if os.path.exists(dest) else 0
        print(f"    download incomplete (rc={rc}, size={cur}/{expect}); resume ({i+1}/{tries})")
        if i < tries - 1:
            time.sleep(2)
    # Fallback: urllib streaming (no resume, but sometimes the proxy behaves differently)
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            if os.path.getsize(dest) == expect:
                return True
        except Exception as e:
            print(f"    urllib fallback error: {e}")
        time.sleep(3)
    return False


def resolve_sha(ref):
    if re.fullmatch(r"[0-9a-f]{40}([0-9a-f]{24})?", ref or ""):
        return ref
    c = api("GET", f"/commits/{urllib.parse.quote(ref, safe='')}")
    return c["sha"]


def all_releases_by_tag():
    rels = api("GET", "/releases?per_page=100")
    return {r["tag_name"]: r for r in rels}


def main():
    os.makedirs(CACHE, exist_ok=True)
    by_tag = all_releases_by_tag()
    print(f"Current releases ({len(by_tag)}):")
    for t, r in sorted(by_tag.items()):
        print(f"  {r['id']} {t} assets={len(r.get('assets', []))}")

    # 1) Remove the stray empty release (it was incorrectly the Latest).
    #    Only act on a release that still has 0 assets (the known broken artifact).
    if STRAY_TAG in by_tag:
        stray = by_tag[STRAY_TAG]
        if len(stray.get("assets", [])) == 0:
            print(f"\n[stray] delete empty release {stray['id']} tag={STRAY_TAG}")
            if not DRY:
                api("DELETE", f"/releases/{stray['id']}")
                api("DELETE", f"/git/refs/tags/{STRAY_TAG}")
            print("  done")
        else:
            print(f"\n[stray] {STRAY_TAG} now has assets (legit migrated release); leave it alone")
    else:
        print(f"\n[stray] {STRAY_TAG} not present, skip")

    by_tag = all_releases_by_tag()  # refresh

    # 2) Migrate each pair, oldest -> newest.
    for old_tag, new_tag in MAPPING:
        if old_tag not in by_tag:
            print(f"\n[skip] source {old_tag} already gone (migrated?)")
            continue
        # If new tag already exists and is healthy, skip.
        if new_tag in by_tag and new_tag != old_tag:
            exist = by_tag[new_tag]
            if len(exist.get("assets", [])) == len(by_tag[old_tag].get("assets", [])):
                print(f"\n[skip] {new_tag} already exists with same asset count")
                continue
            print(f"\n[repair] {new_tag} exists but broken; deleting it first")
            if not DRY:
                api("DELETE", f"/releases/{exist['id']}")
                api("DELETE", f"/git/refs/tags/{new_tag}")

        src = by_tag[old_tag]
        assets = src.get("assets", [])
        print(f"\n--- {old_tag} -> {new_tag}  (assets={len(assets)}) ---")
        if DRY:
            for a in assets:
                print(f"    (dry) would download+upload {a['name']} ({a['size']} B)")
            continue

        # download
        dldir = os.path.join(CACHE, old_tag)
        os.makedirs(dldir, exist_ok=True)
        local = []
        for a in assets:
            p = os.path.join(dldir, a["name"])
            if os.path.exists(p) and os.path.getsize(p) == a["size"]:
                print(f"  reuse {a['name']}")
            else:
                print(f"  download {a['name']} ({a['size']} B)")
                if not download(a["browser_download_url"], p, a["size"]):
                    print(f"  !! download failed for {a['name']}; ABORT")
                    sys.exit(1)
            local.append((p, a["name"], a.get("content_type", "application/octet-stream")))

        sha = resolve_sha(src.get("target_commitish") or src.get("commit", {}).get("sha"))
        new_rel = api("POST", "/releases", {
            "tag_name": new_tag,
            "target_commitish": sha,
            "name": src.get("name") or new_tag,
            "body": src.get("body", ""),
            "draft": False,
            "prerelease": False,
        })
        new_id = new_rel["id"]
        # upload assets to the correct host (with retry; clean up on hard failure)
        try:
            for p, aname, ctype in local:
                with open(p, "rb") as f:
                    data = f.read()
                api_upload(f"/releases/{new_id}/assets?name={urllib.parse.quote(aname)}",
                           data, ctype, aname)
        except Exception as e:
            print(f"  !! upload failed ({e}); removing partial new release {new_id}")
            try:
                api("DELETE", f"/releases/{new_id}")
            except Exception:
                pass
            try:
                api("DELETE", f"/git/refs/tags/{new_tag}")
            except Exception:
                pass
            sys.exit(1)
        # verify
        chk = api("GET", f"/releases/{new_id}")
        got = len(chk.get("assets", []))
        if got != len(assets):
            print(f"  !! asset count mismatch ({got} != {len(assets)}); ABORT, old kept")
            sys.exit(1)
        print(f"  verified {got} assets on new release {new_id}")
        # delete old release + tag
        api("DELETE", f"/releases/{src['id']}")
        api("DELETE", f"/git/refs/tags/{old_tag}")
        print(f"  deleted old release {src['id']} / tag {old_tag}")

    # 3) Ensure the newest is marked Latest.
    by_tag = all_releases_by_tag()
    if LATEST_NEW in by_tag:
        if DRY:
            print(f"\n[latest] (dry) would mark {LATEST_NEW} as latest")
        else:
            try:
                api("PATCH", f"/releases/{by_tag[LATEST_NEW]['id']}", {"make_latest": True})
                print(f"\n[latest] marked {LATEST_NEW} as latest")
            except Exception as e:
                print(f"\n[latest] PATCH failed ({e}); latest should already be correct by creation order")

    # 4) Remove orphan tags left from prior failed runs (old jmgo-* tags with no release).
    try:
        rels = api("GET", "/releases?per_page=100")
        release_tags = {r["tag_name"] for r in rels}
        refs = api("GET", "/git/refs/tags?per_page=100")
        for ref in refs:
            name = ref.get("ref", "").replace("refs/tags/", "")
            if name.startswith("jmgo-") and name not in release_tags:
                print(f"[cleanup] delete orphan tag {name}")
                if not DRY:
                    api("DELETE", f"/git/refs/tags/{name}")
    except Exception as e:
        print(f"[cleanup] skipped: {e}")

    print("\nDONE.")


if __name__ == "__main__":
    main()
