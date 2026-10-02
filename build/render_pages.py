"""Render the whole site into dist/heilbronn/ from the canonical data."""

import hashlib
import html
import json
import pathlib
import re
import shutil

import jinja2

from .derive import derive, symmetry_label
from .families import generate as family_generate
from .ogimage import write_card
from .records_feed import atom, record_events
from .svggen import family_svg, figure_svg

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "sources"
CANONICAL = ROOT / "data" / "canonical"
DIST = ROOT / "dist" / "heilbronn"

VARIANTS = ("square", "triangle", "convex")
NS = list(range(3, 37))  # union over variants; missing docs are skipped
BASE = "/heilbronn"
SITE_ORIGIN = "https://math.tejstead.com"

META = {
    "square": {
        "title": "The Heilbronn Problem for Squares",
        "short": "Square",
        "card_title": "Squares",
        "blurb": "Arranging n points in the unit square to maximize the minimal triangle area.",
        "intro": (
            "<p>Distribute <em>n</em> points in the unit square [0,1]² to maximize the area "
            "A(n) of the smallest triangle formed by any three points. Optimality is formally "
            "proven for n ≤ 9; for n ≥ 10, the values shown represent the current best-known "
            "configurations found by numerical search and geometric construction.</p>"),
    },
    "triangle": {
        "title": "The Heilbronn Problem for Triangles",
        "short": "Triangle",
        "card_title": "Triangles",
        "blurb": "Optimal point arrangements in a triangle of unit area.",
        "intro": (
            "<p>Place <em>n</em> points in a triangle of unit area. Because the problem is "
            "invariant under affine transformations, the specific triangle shape does not affect "
            "the normalized area: coordinates are stored in the standard right triangle "
            "(0,0), (1,0), (0,1) and displayed as an equilateral figure. Note that literature "
            "using the unnormalized right triangle with vertices (0,0),(1,0),(0,1) has area 1/2, "
            "and therefore reports values exactly half of those shown here. Optimality is proven "
            "for n ≤ 8.</p>"),
    },
    "convex": {
        "title": "The Heilbronn Problem for Convex Regions",
        "short": "Convex",
        "card_title": "Convex regions",
        "blurb": "Maximizing minimal triangle area when the convex container is optimized freely.",
        "intro": (
            "<p>In this variant, the enclosing container is itself optimized: the points may lie "
            "in <em>any</em> convex region of unit area. Because any area outside the points' "
            "convex hull only decreases the normalized ratio, the optimal container is always "
            "the convex hull of the point set itself. The objective A is thus the minimal triangle "
            "area divided by the convex hull area. Optimality has been established for n ≤ 8.</p>"),
    },
}

INDEX_THUMBS = {"square": 16, "triangle": 9, "convex": 18}


def load_docs():
    docs = {}
    for v in VARIANTS:
        for n in NS:
            p = CANONICAL / v / f"n{n:02d}.json"
            if p.exists():
                docs[(v, n)] = json.loads(p.read_text())
    return docs


def hash_assets():
    """Copy css/js into dist with content-hashed names; return the map."""
    assets = {}
    outdir = DIST / "assets"
    outdir.mkdir(parents=True, exist_ok=True)
    for src in list((ROOT / "assets" / "css").glob("*.css")) + \
               list((ROOT / "assets" / "js").glob("*.js")):
        digest = hashlib.sha256(src.read_bytes()).hexdigest()[:10]
        hashed = f"{src.stem}.{digest}{src.suffix}"
        shutil.copy(src, outdir / hashed)
        assets[src.name] = hashed
    return assets


SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def pretty_poly(p):
    """152*x**3 + 12*x**2 - 14*x + 1  ->  152x³ + 12x² − 14x + 1"""
    if not p:
        return None
    import re
    s = p.replace("**", "^").replace("*", "")
    s = re.sub(r"\^(\d+)", lambda m: m.group(1).translate(SUPERSCRIPT), s)
    return s.replace("-", "−")


def short_value(doc, digits=8):
    d = doc["value"].get("exact_decimal") or doc["value"]["decimal"]
    if d is None:
        return "?"
    if len(d) <= digits + 2:
        return d
    return d[: digits + 2]


def fmt_dec(dec, limit=18):
    """Decimal for display: exact terminating decimals lose their trailing
    zeros ("0.5", not "0.5000000000000000…"); everything else truncates to
    `limit` characters with an ellipsis."""
    if dec is None:
        return None
    stripped = dec.rstrip("0")
    if stripped.endswith("."):
        stripped = stripped[:-1]
    if len(stripped) <= limit and stripped != dec:
        return stripped
    return (dec[:limit] + "…") if len(dec) > limit else dec


def card_value(doc):
    """Value for a preview card: 8 decimals, with an ellipsis when cut."""
    full = (doc["value"].get("exact_decimal") or doc["value"]["decimal"]).rstrip("0")
    short = short_value(doc)
    return short if len(full) <= len(short) else short + "…"


def fixed8(doc):
    """Uniform 8-decimal rendering for the values table (truncated, which
    keeps every entry a valid lower bound)."""
    d = doc["value"].get("exact_decimal") or doc["value"]["decimal"]
    if d is None:
        return None
    if "." not in d:
        d += "."
    head, tail = d.split(".", 1)
    return f"{head}.{(tail + '00000000')[:8]}"


def credit_text(doc):
    c = doc["credit"]
    if c["trivial"]:
        return "Trivial"
    parts = []
    if c["found"]:
        parts.append(f"{c['found']['name']}" + (f", {c['found']['date']}" if c["found"]["date"] else ""))
    if c["proved"]:
        parts.append(f"proved {c['proved']['name']}" + (f" {c['proved']['date']}" if c["proved"]["date"] else ""))
    return "; ".join(parts) if parts else "—"


def provenance_lines(doc, derived):
    lines = []
    c = doc["credit"]
    if c["trivial"]:
        lines.append("Trivial configuration.")
    if c["found"]:
        lines.append(f"Found by <strong>{c['found']['name']}</strong>"
                     + (f", {c['found']['date']}" if c["found"]["date"] else "") + ".")
    if c["proved"]:
        proof = doc.get("proof")
        head = "Proved optimal"
        if proof and proof.get("url"):
            head = f'<a href="{html.escape(proof["url"], quote=True)}">Proved optimal</a>'
        lines.append(f"{head} by <strong>{c['proved']['name']}</strong>"
                     + (f", {c['proved']['date']}" if c["proved"]["date"] else "") + ".")
    for note in doc.get("notes", []):
        lines.append(note)
    src = doc.get("coordinates_source")
    if src:
        kind_text = {
            "author": "from this site's companion repository",
            "spiralulam": "from spiralulam/heilbronn (MIT)",
            "alphaevolve": "as published by AlphaEvolve (Google DeepMind)",
            "exact-construction": "generated from the exact construction",
            "reconstructed": "reconstructed by local optimization",
            "paper": "exact, as published in",
            "external": "by an external contributor, re-verified here",
        }.get(src["kind"], src["kind"])
        if src["kind"] == "external" and (src.get("ref") or "").startswith("this site's search campaign"):
            kind_text = "from this site's companion repository, re-verified here"
        # ref and note flow in from source meta.json files — for the
        # "external" kind that is contributor-supplied text, and provenance
        # lines render with |safe, so escape rather than trust it.
        note = f" — {html.escape(src['note'])}" if src.get("note") else ""
        lines.append(f"Coordinates {kind_text}: <code>{html.escape(src['ref'])}</code>{note}.")
    if doc.get("verify"):
        v = doc["verify"]
        lines.append(
            f"Verified in exact arithmetic: all {v['triples_checked']} triples "
            f"enumerated, {v['num_min_ties']} tied at the minimum.")
    return lines


def symmetry_text(doc, derived):
    label = doc["symmetry"]["reported"]
    if derived is None:
        return f"Reported symmetry: {label}." if label else "Unknown."
    sym = derived["symmetry"]
    det = symmetry_label(sym, doc["variant"])
    if sym.get("approx"):
        txt = (f"Approximately {det[0].lower()}{det[1:]} (group {sym['group']}: the "
               f"configuration sits within ~10⁻⁴ of exact symmetry, but the optimum "
               f"is not exactly symmetric at coordinate precision).")
    else:
        txt = f"{det} (group {sym['group']}, order {sym['order']})."
    return txt


def _same_symmetry_label(a, b):
    """The historical convex labels wrote "No symmetry" where the square and
    triangle labels (and ours) say "Not symmetric" — the same statement."""
    def norm(s):
        s = s.rstrip(".").strip().lower()
        return "not symmetric" if s == "no symmetry" else s
    return norm(a) == norm(b)


def sym_controls(derived):
    if derived is None:
        return []
    sym = derived["symmetry"]
    if sym["rotation"] or sym["axes"]:
        return [{"key": "axes", "label": "show symmetry elements"}]
    return []


def orbit_text(derived):
    """"18 points in 2 orbits (12 + 6)" — or None when trivial."""
    if derived is None:
        return None
    obs = derived.get("orbits") or []
    if not obs or all(len(o) == 1 for o in obs):
        return None
    sizes = sorted((len(o) for o in obs), reverse=True)
    n = sum(sizes)
    return (f"{n} points in {len(sizes)} orbit{'s' if len(sizes) != 1 else ''} "
            f"({' + '.join(map(str, sizes))}) — hover a point to see its orbit.")


MAX_CC = 6  # keep in sync with svggen.MAX_CC


def single_color(derived):
    classes = derived["classes"]
    return len(classes) > MAX_CC or all(len(c["triangles"]) == 1 for c in classes)


def class_rows(derived):
    if derived is None:
        return []
    single = single_color(derived)
    rows = []
    for i, cls in enumerate(derived["classes"]):
        rows.append({
            "cc": 0 if single else i,
            "swatch": not single,
            "count": len(cls["triangles"]),
            "sides": " · ".join(f"{s:.4f}" for s in cls["sides"]),
            "tris": "  ".join("(" + ",".join(map(str, t)) + ")" for t in cls["triangles"][:12])
                    + ("  …" if len(cls["triangles"]) > 12 else ""),
        })
    return rows


def render_all(env, docs, derived_map, assets):
    common = {
        "base": BASE,
        "site_origin": SITE_ORIGIN,
        "assets": assets,
    }

    # Per-config pages.
    for (v, n), doc in docs.items():
        derived = derived_map.get((v, n))
        figure = None
        family = None
        fam_spec = None
        if doc["points"]:
            figure = figure_svg(v, doc["points"], derived, svg_id="fig")
            fam_spec = family_generate(v, n, doc)
            if fam_spec:
                fsvg, payload = family_svg(v, doc["points"], derived, fam_spec)
                family = {
                    "svg": fsvg,
                    "caption": fam_spec["caption"],
                    "param": fam_spec["param"],
                    "stored_tick": round(fam_spec["param"]["stored_at"] * 1000),
                    "json": json.dumps(payload, separators=(",", ":"))
                            .replace("</", "<\\/"),
                }
        avail = [m for m in NS if (v, m) in docs]
        idx = avail.index(n)
        refs = []
        bib = json.loads((ROOT / "data" / "curated" / "references.json").read_text())["bib"]
        for rid in doc.get("references", []):
            if rid in bib:
                refs.append(bib[rid])
        val = doc["value"]
        exact_dec = val.get("exact_decimal")
        coord_dec = val.get("decimal")
        if derived:
            cls = class_rows(derived)
            if single_color(derived):
                fig_caption = (f"{len(derived['ties'])} triangles tie for the minimal area."
                               if len(derived["ties"]) > 1 else "A unique minimal triangle.")
            else:
                fig_caption = (f"{len(derived['ties'])} minimal triangles in "
                               f"{len(cls)} congruence classes, colored by class.")
        else:
            cls, fig_caption = [], ""
        ctx = dict(common,
            section=v, slug=v, n=n,
            page_path=f"{BASE}/{v}/{n}/",
            og_image=f"{BASE}/{v}/{n}/og.png" if figure else f"{BASE}/{v}/og.png",
            variant_title=META[v]["short"],
            status=doc["status"],
            recon=recon_label(doc),
            exact_display=val.get("exact_display"),
            exact_mathml=val.get("exact_mathml"),
            poly_mathml=val.get("poly_mathml"),
            exact_decimal=exact_dec,
            value_head=(coord_dec[:17] + "…") if coord_dec and len(coord_dec) > 17 else coord_dec,
            value_full=coord_dec,
            value_fraction=val.get("fraction"),
            value_short=short_value(doc),
            poly=pretty_poly(val.get("minimal_polynomial")),
            poly_which=(val.get("exact_poly") or {}).get("which"),
            poly_note=(val.get("exact_poly") or {}).get("note"),
            figure=figure,
            fig_caption=fig_caption,
            classes=cls,
            tie_count=len(derived["ties"]) if derived else 0,
            sym_controls=sym_controls(derived),
            symmetry_text=symmetry_text(doc, derived),
            orbit_line=orbit_text(derived),
            provenance=provenance_lines(doc, derived),
            changelog=[{"date": e.get("date", ""), "text": e.get("text", e.get("note", ""))}
                       for e in doc.get("changelog", [])],
            downloads=([
                {"href": "points.txt", "label": "points.txt", "note": "coordinates, tab-separated"},
                {"href": "points.csv", "label": "points.csv", "note": "coordinates, CSV"},
                {"href": "points.json", "label": "points.json", "note": "full record: value, provenance, verification"},
                {"href": "figure.svg", "label": "figure.svg", "note": "this figure"},
            ] + ([
                {"href": "family.json", "label": "family.json",
                 "note": "the optimal family: exact endpoints, 30-decimal sample members"},
            ] if family else []) if doc["points"] else []),
            family=family,
            references=refs,
            prev=avail[idx - 1] if idx > 0 else None,
            next=avail[idx + 1] if idx + 1 < len(avail) else None,
            cross=[{"slug": w, "title": META[w]["short"]} for w in VARIANTS if w != v and (w, n) in docs],
        )
        out = DIST / v / str(n) / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(env.get_template("config.html").render(ctx))
        if figure:
            (out.parent / "figure.svg").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n' + figure)
            write_card(out.parent / "og.png", figure, f"{META[v]['short']}, n = {n}",
                       f"A = {card_value(doc)}",
                       "proven optimal" if doc["status"] == "proven" else "best known")
        if fam_spec:
            (out.parent / "family.json").write_text(json.dumps({
                "variant": v, "n": n,
                "param": fam_spec["param"],
                "moving": fam_spec["moving"],
                "samples": fam_spec["samples"],
                "caption": fam_spec["caption"],
                "verification": (
                    "each sample's 30-decimal literals verified in exact "
                    "arithmetic to within relative 1e-20 of the stored "
                    "configuration's exact value at build time"),
            }, indent=1))

    # Variant pages: one long page of classic entry rows, one per n.
    for v in VARIANTS:
        entries = []
        for n in NS:
            doc = docs.get((v, n))
            if not doc:
                continue
            derived = derived_map.get((v, n))
            val = doc["value"]
            dec = val.get("exact_decimal") or val.get("decimal")
            # Rendered with |safe (for the proof link), so escape the names.
            credit_lines = []
            c = doc["credit"]
            if c["trivial"]:
                credit_lines.append("Trivial.")
            if c["found"]:
                credit_lines.append(f"Found by {html.escape(c['found']['name'])}"
                                    + (f", {html.escape(c['found']['date'])}" if c["found"]["date"] else "") + ".")
            if c["proved"]:
                proof = doc.get("proof")
                head = "Proved optimal"
                if proof and proof.get("url"):
                    head = f'<a href="{html.escape(proof["url"], quote=True)}">Proved optimal</a>'
                credit_lines.append(f"{head} by {html.escape(c['proved']['name'])}"
                                    + (f", {html.escape(c['proved']['date'])}" if c["proved"]["date"] else "") + ".")
            symline = None
            if derived:
                sym = derived["symmetry"]
                det = symmetry_label(sym, v)
                if sym.get("approx"):
                    det = "approximately " + det[0].lower() + det[1:]
                ties = len(derived["ties"])
                symline = f"{det} · {ties} minimal triangle{'s' if ties != 1 else ''}"
            entries.append({
                "n": n,
                "status": doc["status"],
                "recon": recon_label(doc),
                "fig": (f'<img loading="lazy" width="260" height="260" alt="" '
                        f'src="{BASE}/{v}/{n}/figure.svg">') if doc["points"] else None,
                "mathml": val.get("exact_mathml"),
                "exact_text": None if val.get("exact_mathml") else val.get("exact_display"),
                "poly_mathml": None if val.get("exact_mathml") else val.get("poly_mathml"),
                "dec": fmt_dec(dec),
                "credit_lines": credit_lines,
                "symline": symline,
            })
        ns = [m for m in NS if (v, m) in docs]
        write_card(DIST / v / "og.png", figure_svg(v, docs[(v, INDEX_THUMBS[v])]["points"],
                                                   derived_map[(v, INDEX_THUMBS[v])]),
                   META[v]["card_title"], f"n = {ns[0]} to {ns[-1]}",
                   "best known configurations")
        ctx = dict(common, section=v, slug=v, page_path=f"{BASE}/{v}/",
                   og_image=f"{BASE}/{v}/og.png",
                   title=META[v]["title"], intro=META[v]["intro"],
                   intro_plain=META[v]["blurb"], entries=entries)
        out = DIST / v / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(env.get_template("variant.html").render(ctx))

    # Index.
    variants_ctx = []
    for v in VARIANTS:
        tn = INDEX_THUMBS[v]
        variants_ctx.append({
            "slug": v, "title": META[v]["card_title"], "blurb": META[v]["blurb"],
            "thumb": f'<img width="220" height="220" alt="" src="{BASE}/{v}/{tn}/figure.svg">',
        })
    value_rows = []
    for n in NS:
        cells = []
        for v in VARIANTS:
            doc = docs.get((v, n))
            cells.append({
                "slug": v,
                "display": fixed8(doc),
                "proven": doc["status"] in ("proven", "trivial"),
            } if doc else None)
        value_rows.append({"n": n, "cells": cells})
    write_card(DIST / "og.png", figure_svg("square", docs[("square", 16)]["points"],
                                           derived_map[("square", 16)]),
               "Record tables", "n = 3 to 36", "square · triangle · convex")
    events = record_events()
    (DIST / "records.xml").write_text(atom(events, SITE_ORIGIN, BASE))
    recent = [{
        "date": e["date"][:10], "slug": e["variant"], "n": e["n"],
        "title": META[e["variant"]]["short"], "value": e["new"][:10],
        "gain": f"+{float(e['gain']) * 100:.2f}%", "credit": e["credit"],
    } for e in events[:10]]
    ctx = dict(common, section="index", page_path=f"{BASE}/", variants=variants_ctx,
               value_rows=value_rows, recent=recent)
    (DIST / "index.html").write_text(env.get_template("index.html").render(ctx))


RECON_LABELS = {
    "figure": "re-derived from figure",
    "value-and-symmetry": "re-derived (value + symmetry)",
    "tightened-original": "tightened originals",
    "original-this-site": "new configuration (this site)",
}


def recon_label(doc):
    """None when coordinates are originals; otherwise a tag naming exactly
    how much reconstruction was involved."""
    src = doc.get("coordinates_source") or {}
    if src.get("kind") != "reconstructed":
        return None
    return RECON_LABELS.get(src.get("basis"), "reconstructed coords")


METHODS_BODY = """
<p>This site is an open, fully reproducible archive of best-known configurations
for the Heilbronn problem. Every figure, table, and data download is compiled directly
from exact coordinate records. All data, search tools, and exact verification pipelines
are open source in <a href="https://github.com/tejstead/heilbronn-site">tejstead/heilbronn-site</a>,
meaning any result on this site can be verified independently on your own machine.</p>

<h2>Where the coordinates come from</h2>
<ul>
<li><strong>Community contributions</strong> — new configurations and exact
algebraic proofs are submitted via pull requests (see <a href="https://github.com/tejstead/heilbronn-site/blob/main/CONTRIBUTING.md">CONTRIBUTING</a>).
Continuous integration computes all triangle areas in exact rational arithmetic and posts
an automated verification report on the PR. Recent record submissions include contributions
from Nathan Sudermann-Merx, Rhys Chappell, and Chouaieb Nemri.</li>
<li><strong>This site's own search campaigns</strong> — records for
n = 17…36 across the variants, found with the toolkit under
<code>search/</code> and submitted through the same lane as everyone else's.</li>
<li><a href="https://github.com/cnemri/heilbronn-alphaevolve">cnemri/heilbronn-alphaevolve</a>
— Chouaieb Nemri's AlphaEvolve-evolved search program (square n = 17, 21, 22
records); the evolved program's architecture also powers several of the later
batch records.</li>
<li><a href="https://github.com/spiralulam/heilbronn">spiralulam/heilbronn</a>
(MIT) — companion repository to Nathan Sudermann-Merx's certified-optimality
papers: square n = 3…16, including the previously unpublished configurations
of Peter Karpov and Mark Beyleveld. His original coordinates for later
entries were also submitted here directly.</li>
<li><a href="https://github.com/rhyschappell/heilbronn-n14-exact">rhyschappell/heilbronn-n14-exact</a>
— Rhys Chappell's exact algebraic realization of the n = 14 square
configuration; he has since contributed further records and the degree-15
exact value for square n = 24.</li>
<li><a href="https://github.com/google-deepmind/alphaevolve_results">google-deepmind/alphaevolve_results</a>
— the original AlphaEvolve constructions (triangle n = 11, convex n = 13, 14).</li>
<li>Published exact constructions from the proofs (see the bibliography).</li>
<li>Local reconstruction: for configurations whose coordinates were never
published (mostly David Cantrell's), we re-derive them by numerical
optimization seeded from the record figures, and accept a reconstruction
only if its exact value and symmetry match the record entry. These are
labeled <em>reconstructed</em> and never claim to be the original author's
exact arrangement.</li>
</ul>

<h2>How New Records Are Discovered</h2>
<p>Finding candidate configurations requires navigating high-dimensional, non-convex
landscapes where local optima proliferate rapidly. The repository includes an optimization
toolkit (under <code>search/</code>) employing several complementary strategies:</p>
<ul>
  <li><strong>Basin-hopping &amp; Local Search (<code>attack.py</code>):</strong> Alternates random coordinate perturbations with local minimization to escape shallow basins.</li>
  <li><strong>Successive Linear Programming (<code>refine.py</code>):</strong> Uses trust-region SLP polishing with Karush-Kuhn-Tucker (KKT) tightening to drive candidate coordinates to machine precision.</li>
  <li><strong>Symmetry Restriction (<code>sym.py</code>):</strong> Restricts point placements to candidate point groups (such as dihedral and cyclic symmetries), drastically reducing the dimension of the search space.</li>
  <li><strong>Laddering &amp; Seeding:</strong> Bootstraps an n-point configuration by strategically inserting an additional point into the (n-1) optimum and re-optimizing.</li>
  <li><strong>Evolved Heuristics:</strong> Several recent records (e.g. square n = 17, 21, and 22) originated from heuristic search algorithms generated by DeepMind's AlphaEvolve system, executed and refined by community contributors.</li>
</ul>

<h2>Exact Algebraic Values</h2>
<p>Whenever a configuration has an exact closed form, we determine its minimal polynomial
through one of three paths: formal optimality proofs from the literature, polynomials
provided by contributors (validated to 45 digits at build time), or direct symbolic
derivation. For derived values, we identify the tightest triangle constraints, reduce them
by the configuration's symmetry group, and solve the polynomial tie system using Gröbner
bases followed by linear programming for any interior slack points.</p>
<p>This process yielded the degree-5 quintic for triangle n&nbsp;=&nbsp;15 and the cubics for square
n&nbsp;=&nbsp;10 and 12. In cases where a polynomial's Galois group is not solvable by radicals,
algebraic theory prohibits any closed form in terms of nested roots; for those entries,
we report the root of the minimal polynomial directly.</p>

<h2>Verification</h2>
<p>Every configuration on this site is checked with exact rational
arithmetic: the coordinates' decimal literals are taken exactly, all C(n,3)
triangle areas are enumerated, and the reported value is the exact minimum,
normalized to a unit-area container. Two independent verifiers
(<code>search/verify_a.py</code>, <code>search/verify_b.py</code>) agree on
every entry; the build runs a library form of the first, submissions are
re-verified by CI, and the in-browser
<a href="/heilbronn/verifier/">verifier</a> runs the same computation.</p>

<h2>Normalization conventions</h2>
<p>The container has <strong>unit area</strong>. Beware when comparing with papers: work in the unit
<em>right</em> triangle (area ½) quotes triangle values half as large, and the
retired circle variant used a unit-<em>radius</em> disk (area π). The triangle
problem is affine-invariant, so coordinates are stored in the right frame
(0,0),(1,0),(0,1) and displayed equilateral.</p>

<h2>Historical Origin &amp; Attribution</h2>
<p>These record tables build on the work of Erich Friedman, whose Packing Center
cataloged Heilbronn configurations for decades before going offline in 2026.
We preserved his historical records, attribution notes, and symmetry classifications
in <code>data/curated/records.json</code>. All figures on this site are generated
anew from verified coordinate sets. Individual record holders and proof credits
are tracked on the <a href="/heilbronn/leaderboard/">leaderboard</a>.</p>
"""




def render_extra(env, assets, values_name):
    """Pages that need the values.json asset name (written by downloads)."""
    common = {"base": BASE, "site_origin": SITE_ORIGIN, "assets": assets}
    from .charts import build_charts
    (DIST / "trends").mkdir(parents=True, exist_ok=True)
    (DIST / "trends" / "index.html").write_text(
        env.get_template("trends.html").render(
            dict(common, section="trends", page_path=f"{BASE}/trends/",
                 charts=build_charts(load_docs()))))
    bib = json.loads((ROOT / "data" / "curated" / "references.json").read_text())["bib"]
    (DIST / "methods").mkdir(parents=True, exist_ok=True)
    (DIST / "methods" / "index.html").write_text(
        env.get_template("methods.html").render(
            dict(common, section="methods", page_path=f"{BASE}/methods/",
                 body=METHODS_BODY, bib=list(bib.values()))))
    from .leaderboard import leaderboards
    (DIST / "leaderboard").mkdir(parents=True, exist_ok=True)
    (DIST / "leaderboard" / "index.html").write_text(
        env.get_template("leaderboard.html").render(
            dict(common, section="leaderboard", page_path=f"{BASE}/leaderboard/",
                 boards=leaderboards(load_docs()))))
    (DIST / "verifier").mkdir(parents=True, exist_ok=True)
    (DIST / "verifier" / "index.html").write_text(
        env.get_template("verifier.html").render(
            dict(common, section="verifier", page_path=f"{BASE}/verifier/",
                 values_name=values_name)))
    write_sitemap_and_404(env, common)


def write_sitemap_and_404(env, common):
    urls = [f"{BASE}/", f"{BASE}/trends/", f"{BASE}/leaderboard/",
            f"{BASE}/verifier/", f"{BASE}/methods/"]
    for v in VARIANTS:
        urls.append(f"{BASE}/{v}/")
        for n in NS:
            if (DIST / v / str(n) / "index.html").exists():
                urls.append(f"{BASE}/{v}/{n}/")
    body = "\n".join(
        f"  <url><loc>{SITE_ORIGIN}{u}</loc></url>" for u in urls)
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n")
    (DIST / "404.html").write_text(env.get_template("404.html").render(common))
    (DIST.parent / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_ORIGIN}{BASE}/sitemap.xml\n")


def make_env():
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(ROOT / "templates"),
        autoescape=True, trim_blocks=True, lstrip_blocks=True)


def render(docs=None, derived_map=None):
    docs = docs or load_docs()
    if derived_map is None:
        derived_map = {}
        for key, doc in docs.items():
            if doc["points"]:
                derived_map[key] = derive(key[0], doc["points"])
    env = make_env()
    assets = hash_assets()
    render_all(env, docs, derived_map, assets)
    return docs, derived_map, assets, env
