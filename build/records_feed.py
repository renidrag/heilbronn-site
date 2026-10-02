"""Record history from git: every commit that raised an entry's value in
data/canonical is a new record. Feeds the home page's recent-records list
and the Atom feed. The curated changelog can't serve here — it is written
by hand and misses records merged through submissions.

Needs full history; a shallow clone fails the build rather than publishing
an empty feed (CI checks out with fetch-depth: 0). Uncommitted canonical
rows count too, so a record is in the feed from the build that ingests it."""

import html
import json
import pathlib
import subprocess
from datetime import datetime
from decimal import Decimal

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Same rule as the tie tolerance: re-polishing coordinates moves a value in
# its far digits, which is not a new record.
MIN_GAIN = Decimal("1e-9")
# Names that were corrected in canonical after a record had already been
# superseded, so no later revision of that record carries the fix (25d8802).
CREDIT_FIXES = {"Fable51": "Fable 5.1 with Shengtong Zhang"}


def _git(*args, stdin=None):
    return subprocess.run(["git", *args], cwd=ROOT, input=stdin,
                          capture_output=True, check=True).stdout


def _revisions():
    """[(sha, iso_date, [paths])] touching data/canonical, oldest first."""
    if _git("rev-parse", "--is-shallow-repository").strip() == b"true":
        raise SystemExit("records feed: shallow clone — check out with fetch-depth: 0")
    out = _git("log", "--reverse", "--format=@%H %aI", "--name-only",
               "--", "data/canonical").decode()
    revs = []
    for line in out.splitlines():
        if line.startswith("@"):
            sha, date = line[1:].split()
            revs.append((sha, date, []))
        elif line.strip().endswith(".json"):
            revs[-1][2].append(line.strip())
    return revs


def _blobs(specs):
    """Contents of many "sha:path" specs in one git process (None if absent)."""
    out = _git("cat-file", "--batch", stdin="".join(s + "\n" for s in specs).encode())
    docs, pos = [], 0
    for _ in specs:
        nl = out.index(b"\n", pos)
        header = out[pos:nl].split()
        if header[-1] == b"missing":
            docs.append(None)
            pos = nl + 1
            continue
        size = int(header[2])
        docs.append(json.loads(out[nl + 1:nl + 1 + size]))
        pos = nl + 1 + size + 1
    return docs


def record_events():
    """All record improvements, newest first: dicts with date, variant, n,
    old, new (decimal strings), gain (relative), credit, sha."""
    revs = _revisions()
    specs = [(sha, date, path) for sha, date, paths in revs for path in paths]
    docs = _blobs([f"{sha}:{path}" for sha, _, path in specs])
    # Ingest has just rewritten data/canonical; publish-site commits it only
    # after the build. Count those rows now, dated at the merge (HEAD).
    dirty = _git("status", "--porcelain", "--", "data/canonical").decode().splitlines()
    if dirty:
        head_date = _git("log", "-1", "--format=%aI").decode().strip()
        for line in dirty:
            path = line[3:]
            if path.endswith(".json") and (ROOT / path).exists():
                specs.append(("worktree", head_date, path))
                docs.append(json.loads((ROOT / path).read_text()))
    best, events, holder = {}, [], {}
    for (sha, date, _), doc in zip(specs, docs):
        if not doc or not doc.get("points") or doc["value"].get("decimal") is None:
            continue
        key = (doc["variant"], doc["n"])
        dec = doc["value"]["decimal"]
        value = Decimal(dec)
        name = ((doc.get("credit") or {}).get("found") or {}).get("name")
        prev = best.get(key)
        if prev is not None and value > prev[0] * (1 + MIN_GAIN):
            holder[key] = {"date": date, "variant": key[0], "n": key[1],
                           "old": prev[1], "new": dec, "gain": value / prev[0] - 1,
                           "sha": sha}
            events.append(holder[key])
        if key in holder:
            # Credits get corrected after the fact; the newest revision of
            # the same record has the right name.
            holder[key]["credit"] = CREDIT_FIXES.get(name, name)
        if prev is None or value > prev[0]:
            best[key] = (value, dec)
    events.sort(key=lambda e: datetime.fromisoformat(e["date"]), reverse=True)
    return events


def atom(events, origin, base, limit=50):
    """Atom 1.0 feed of the newest `limit` records."""
    def esc(s):
        return html.escape(str(s), quote=True)
    entries = []
    for e in events[:limit]:
        url = f"{origin}{base}/{e['variant']}/{e['n']}/"
        title = (f"{e['variant'].title()}, n = {e['n']}: {e['new'][:12]} "
                 f"(+{float(e['gain']) * 100:.3g}%)")
        summary = (f"New best known value {e['new'][:20]}, up from {e['old'][:20]}"
                   + (f"; found by {e['credit']}" if e["credit"] else "") + ".")
        entries.append(
            "<entry>"
            # Keyed by value, not commit: ids survive a history rewrite.
            f"<id>{esc(url)}#A={e['new'][:16]}</id>"
            f"<title>{esc(title)}</title>"
            f'<link rel="alternate" href="{esc(url)}"/>'
            f"<updated>{e['date']}</updated>"
            + (f"<author><name>{esc(e['credit'])}</name></author>" if e["credit"] else "")
            + f"<summary>{esc(summary)}</summary>"
            "</entry>")
    updated = events[0]["date"] if events else "1970-01-01T00:00:00Z"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        f"<id>{origin}{base}/</id>"
        "<title>Heilbronn problem: new records</title>"
        f'<link rel="self" href="{origin}{base}/records.xml"/>'
        f'<link rel="alternate" href="{origin}{base}/"/>'
        "<author><name>Heilbronn record tables</name></author>"
        f"<updated>{updated}</updated>"
        + "\n".join(entries) + "</feed>\n")
