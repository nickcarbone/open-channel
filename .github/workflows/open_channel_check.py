#!/usr/bin/env python3
"""Check every Open Channel feed and write open-channel-status.json.

Reads the station list embedded in open-channel.html (the <script id="stations"> block),
opens each stream briefly, and records whether it answered with audio.

Usage: python3 scripts/open_channel_check.py open-channel.html open-channel-status.json
Standard library only, so it runs on a stock GitHub Actions runner.
"""
import json, re, sys, time, datetime, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

UA = "OpenChannel-FeedCheck/1.0 (+https://nickcarbone.github.io/open-channel.html)"

def stream_url(src, key):
    if src == "atc":
        return "https://d.liveatc.net/" + key
    if src == "wx":
        return "https://wxradio.org/" + key
    return "https://broadcastify.cdnstream1.com/" + key

def check(row):
    sid, src, key = row[0], row[10], row[11]
    url = stream_url(src, key)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Icy-MetaData": "0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            ctype = r.headers.get("Content-Type", "")
            chunk = r.read(2048)
            ok = r.status == 200 and len(chunk) > 0 and ("audio" in ctype or "mpeg" in ctype or "ogg" in ctype)
            return sid, {"ok": ok, "code": r.status}
    except urllib.error.HTTPError as e:
        return sid, {"ok": False, "code": e.code}
    except Exception as e:  # timeouts, resets: unknown rather than off air
        return sid, {"ok": False, "code": None, "error": type(e).__name__}

def main(html_path, out_path):
    html = open(html_path, encoding="utf-8").read()
    m = re.search(r'<script type="application/json" id="stations">(.*?)</script>', html, re.S)
    if not m:
        sys.exit("station block not found")
    rows = json.loads(m.group(1))
    # gentle: a few at a time, each connection closed after 2 KB
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(check, rows))
    out = {
        "checked": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "stations": results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    live = sum(1 for v in results.values() if v["ok"])
    print(f"{live}/{len(results)} feeds answered with audio")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "open-channel.html",
         sys.argv[2] if len(sys.argv) > 2 else "open-channel-status.json")
