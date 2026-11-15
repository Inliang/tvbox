#!/usr/bin/env python3
import json, sys, subprocess, urllib.request, urllib.error

REPO = "Inliang/tvbox"
API = f"https://api.github.com/repos/{REPO}"

def token():
    out = subprocess.run(["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n", capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("no token")

TOKEN = token()
HDR = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json", "User-Agent": "ghq"}

def api(method, path):
    req = urllib.request.Request(API + path, headers=HDR, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

mode = sys.argv[1] if len(sys.argv) > 1 else "list"
if mode == "list":
    rels = api("GET", "/releases?per_page=100")
    rels.sort(key=lambda r: r.get("published_at", ""))
    for r in rels:
        print(r["id"], r["tag_name"], "| pub", r.get("published_at"), "| assets", len(r.get("assets", [])),
              "| draft", r.get("draft"), "| pre", r.get("prerelease"))
    print("TOTAL", len(rels))
elif mode == "tags":
    tags = api("GET", "/tags?per_page=100")
    for t in tags:
        print(t["name"], t.get("commit", {}).get("sha", "")[:10])
    print("TOTAL", len(tags))
elif mode == "latest":
    r = api("GET", "/releases/latest")
    print("LATEST", r["id"], r["tag_name"], r.get("published_at"))
elif mode == "detail":
    tag = sys.argv[2]
    r = api("GET", f"/releases/tags/{tag}")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:1500])
