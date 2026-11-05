#!/usr/bin/env python3
"""HTTP liveness sweep over the links in a generated CFP report.

Usage:
  python3 check-links.py REPORT.md [--only SUBSTRING] [--workers 8] [--timeout 20]

Prints one line per non-200 URL and a summary; exits 1 if anything is dead, so it
can gate a rebuild. Keep --workers modest: these are other people's servers.

Reading the result:
  404/410  -> the link is gone (dead CFP page, retired platform).
  403/429  -> blocked or rate-limited, i.e. *unknown*, not dead. Retry later or
              narrow with --only instead of declaring the event unreachable.
"""
import argparse, concurrent.futures, re, sys, urllib.error, urllib.request

UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")}

LINK = re.compile(r"\]\((https?://[^)\s]+)\)")          # markdown links
BARE = re.compile(r"(?<![(\w])(https?://[^\s)|<>\"']+)")  # bare urls
TRAILING = ",.;:!?"


def urls_in(text, only=None):
    found = set(LINK.findall(text)) | set(BARE.findall(text))
    clean = {u.rstrip(TRAILING) for u in found}
    if only:
        clean = {u for u in clean if only in u}
    return sorted(clean)


def check(url, timeout):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return url, r.status, ""
    except urllib.error.HTTPError as e:
        return url, e.code, ""
    except Exception as e:                      # DNS, TLS, timeout, reset
        return url, None, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--only", help="substring filter, e.g. sessionize.com")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=20)
    a = ap.parse_args()

    text = open(a.report, encoding="utf-8").read()
    urls = urls_in(text, a.only)
    print(f"checking {len(urls)} urls from {a.report}"
          + (f" (filter: {a.only})" if a.only else ""))

    with concurrent.futures.ThreadPoolExecutor(a.workers) as ex:
        results = list(ex.map(lambda u: check(u, a.timeout), urls))

    bad = [(u, s, err) for u, s, err in results if s != 200]
    for u, s, err in sorted(bad, key=lambda r: str(r[1])):
        print(f"  {s if s else 'ERR'}  {u}" + (f"   [{err}]" if err else ""))
    print(f"200: {len(results) - len(bad)} | not-200: {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
