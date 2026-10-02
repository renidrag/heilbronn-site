"""Check every external link on the built site (dist/heilbronn).

    python3 scripts/check_external_links.py [--markdown report.md]

A link is dead on 404/410 or when the host doesn't resolve or connect.
Any other failure (403s from publishers behind doi.org that refuse
scripted requests, 429s, 5xx) is listed as unverifiable, not dead.
Exits 1 if anything is dead. Links back to the site itself are skipped:
build.check_links covers those, and new pages aren't deployed yet.
Run weekly by .github/workflows/external-links.yml; the Packing Center
going offline in 2026 is why."""

import argparse
import concurrent.futures
import html.parser
import pathlib
import socket
import sys
import urllib.error
import urllib.request

DIST = pathlib.Path(__file__).resolve().parent.parent / "dist" / "heilbronn"
UA = "Mozilla/5.0 (compatible; heilbronn-link-check; +https://math.tejstead.com/heilbronn/)"
DEAD = {404, 410}
OWN_ORIGIN = "https://math.tejstead.com/"


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if (k in ("href", "src") and v and v.startswith(("http://", "https://"))
                    and not v.startswith(OWN_ORIGIN)):
                self.found.append(v)


def collect():
    """{url: [pages linking to it]}"""
    pages = {}
    for page in sorted(DIST.rglob("*.html")):
        p = Links()
        p.feed(page.read_text())
        for url in p.found:
            pages.setdefault(url.split("#")[0], []).append(
                "/" + str(page.relative_to(DIST.parent)))
    return pages


def status(url):
    """("ok" | "dead" | "blocked", detail). HEAD first, then GET: some
    servers reject HEAD."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return "ok", str(r.status)
        except urllib.error.HTTPError as e:
            fail = e.code
        except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
            fail = str(getattr(e, "reason", e))
    if isinstance(fail, str) or fail in DEAD:
        return "dead", str(fail)
    return "blocked", str(fail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown", help="write a report for the issue body")
    args = ap.parse_args()
    if not DIST.exists():
        sys.exit("build the site first (make build)")
    pages = collect()
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        results = dict(zip(pages, pool.map(status, pages)))
    dead = {u: r for u, r in results.items() if r[0] == "dead"}
    blocked = {u: r for u, r in results.items() if r[0] == "blocked"}
    print(f"{len(pages)} external links: {len(dead)} dead, "
          f"{len(blocked)} unverifiable")
    for u, (_, d) in sorted(dead.items()):
        print(f"DEAD {d}: {u}  (on {', '.join(sorted(set(pages[u]))[:3])})")
    for u, (_, d) in sorted(blocked.items()):
        print(f"unverifiable {d}: {u}")
    if args.markdown:
        lines = [f"The weekly link check found {len(dead)} dead external "
                 f"link{'s' if len(dead) != 1 else ''}.", ""]
        for u, (_, d) in sorted(dead.items()):
            on = sorted(set(pages[u]))
            more = f" and {len(on) - 3} more" if len(on) > 3 else ""
            lines.append(f"- {u} ({d}), linked from {', '.join(on[:3])}{more}")
        pathlib.Path(args.markdown).write_text("\n".join(lines) + "\n")
    sys.exit(1 if dead else 0)


if __name__ == "__main__":
    main()
