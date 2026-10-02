"""Ingest: unify all vendored sources into canonical per-configuration JSONs.

For each (variant, n) the candidates from every source are exactly verified
(vendored verifier, exact rationals) and the best value wins. The result is
written to data/canonical/{variant}/nNN.json and committed, so the rest of
the pipeline — and reviewers — see one schema and reviewable diffs.

Also prints the coverage audit: per row, the chosen source and how our exact
value relates to the value in the record ledger (data/curated/records.json:
the historical values, credits, symmetry labels and notes per entry).

An entry never regresses: the committed canonical row is itself a candidate,
so if a source directory is overwritten with a lower-valued configuration
(typically a submission verified against an older main and merged after a
better one landed in the same directory), the canonical keeps the higher
coordinates and their provenance, and the overwrite is reported as a
REGRESSION line on stderr. To lower an entry on purpose, delete its
data/canonical/ file and re-run.
"""

import json
import pathlib
import re
import sys
from fractions import Fraction

from .vendor.verify_exact import parse_points_text, verify, fraction_to_30sig

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources"
CURATED = ROOT / "data" / "curated"
CANONICAL = ROOT / "data" / "canonical"

VARIANTS = ("square", "triangle", "convex")
# Per-variant n range: the square table runs to 36 (AlphaEvolve submission),
# the other two stop at 35.
N_MAX = {"square": 36, "triangle": 35, "convex": 35}


def ns(variant):
    return range(3, N_MAX[variant] + 1)


NS = range(3, max(N_MAX.values()) + 1)

FRAMES = {"square": "unit-square", "triangle": "right", "convex": "free"}

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
def load_records():
    """The record ledger: per "variant/n", the value the credited record was
    announced with (decimal, lower_bound), the credit (found / proved /
    trivial), the exact form if known, the symmetry label and page notes."""
    return load_curated("records.json")


def load_curated(name):
    p = CURATED / name
    return json.loads(p.read_text()) if p.exists() else {}


def frac_to_dec(fr):
    """Exact decimal string for a Fraction with 10-smooth denominator (all
    source coordinates are decimal literals, so this always applies).
    Integer arithmetic throughout: Decimal division would round to the
    context precision (28 digits) and silently perturb 30-digit literals."""
    num, den = fr.numerator, fr.denominator
    k = 0
    while den % 10 == 0:
        den //= 10
        k += 1
    while den % 2 == 0:
        den //= 2
        num *= 5
        k += 1
    while den % 5 == 0:
        den //= 5
        num *= 2
        k += 1
    if den != 1:
        raise ValueError(f"denominator of {fr} is not 10-smooth")
    sign = "-" if num < 0 else ""
    digits = str(abs(num)).rjust(k + 1, "0")
    if k == 0:
        return sign + digits
    s = sign + digits[:-k] + "." + digits[-k:]
    return s.rstrip("0").rstrip(".") if "." in s else s


def points_to_strings(points):
    return [[frac_to_dec(x), frac_to_dec(y)] for x, y in points]


def eq_to_right_frame(points_str):
    """Exact-decimal conversion from the equilateral frame (0,0),(1,0),
    (1/2,sqrt(3)/2) to the right frame (0,0),(1,0),(0,1):
    x' = x - y/sqrt(3),  y' = 2y/sqrt(3).

    Computed at 50 dps, rounded to 15 decimals, then nudged (in exact
    rationals) back inside the domain if rounding pushed a boundary point
    out. The normalized value is affine-invariant, so this loses ~1e-15 of
    the value at most.
    """
    import mpmath
    mpmath.mp.dps = 50
    s3 = mpmath.sqrt(3)
    out = []
    for xs, ys in points_str:
        x, y = mpmath.mpf(xs), mpmath.mpf(ys)
        xr = x - y / s3
        yr = 2 * y / s3
        out.append([mpmath.nstr(xr, 17, strip_zeros=False),
                    mpmath.nstr(yr, 17, strip_zeros=False)])
    # Round to 15 decimals and repair feasibility exactly.
    step = Fraction(1, 10 ** 15)
    fixed = []
    for xs, ys in out:
        x = round(Fraction(xs), 15) if "." in xs else Fraction(xs)
        y = round(Fraction(ys), 15) if "." in ys else Fraction(ys)
        x = max(x, Fraction(0))
        y = max(y, Fraction(0))
        while x + y > 1:
            if x >= y:
                x -= step
            else:
                y -= step
        fixed.append([fmt15(x), fmt15(y)])
    return fixed


def orient_triangle_mirror(points_str):
    """Triangle configurations with exactly one mirror symmetry are stored
    with that mirror as the vertical axis of the equilateral display, i.e.
    through the apex (0,1) of the right frame. The container's vertex
    permutations are exact, area-preserving affine maps, so this changes no
    value and no digit of precision; it is the identity for configurations
    already oriented that way, and for every other symmetry group."""
    import math
    from .derive import detect_symmetry, TOL
    pts = [(float(x), float(y)) for x, y in points_str]
    sym = detect_symmetry("triangle", pts, tol=TOL)
    if sym["group"] != "D1":
        return points_str
    ang = math.degrees(sym["axes"][0]["angle"]) % 180
    fr = [(Fraction(x), Fraction(y)) for x, y in points_str]
    if abs(ang - 150) < 1e-6:    # mirror fixes vertex (1,0): send it to the apex
        fr = [(1 - x - y, x) for x, y in fr]
    elif abs(ang - 30) < 1e-6:   # mirror fixes vertex (0,0)
        fr = [(y, 1 - x - y) for x, y in fr]
    else:                        # already vertical (90 degrees)
        return points_str
    return [[frac_to_dec(x), frac_to_dec(y)] for x, y in fr]


def fmt15(fr):
    """Format an exact multiple of 1e-15 as a fixed 15-decimal string."""
    scaled = fr * 10 ** 15
    assert scaled.denominator == 1
    sign = "-" if scaled < 0 else ""
    v = abs(int(scaled))
    return f"{sign}{v // 10**15}.{v % 10**15:015d}"


def _external_exact_coeffs(path):
    """Contributor-supplied minimal polynomial (see CONTRIBUTING.md): integer
    coefficients, constant first, in exact.json. Returned as list[int] or
    None. Deliberately data-only — the sympy expression string is built here
    from validated integers, never parsed from contributor text."""
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    raw = data.get("minimal_polynomial")
    if not isinstance(raw, list) or not 2 <= len(raw) <= 65:
        return None
    coeffs = []
    for c in raw:
        if isinstance(c, str) and c.lstrip("-").isdigit():
            c = int(c)
        if not isinstance(c, int) or isinstance(c, bool) or c.bit_length() > 4096:
            return None
        coeffs.append(c)
    return coeffs if coeffs[-1] != 0 else None


def coeffs_to_poly(coeffs):
    terms = []
    for i, c in enumerate(coeffs):
        if c == 0:
            continue
        if i == 0:
            terms.append(str(c))
        elif i == 1:
            terms.append(f"{c}*x")
        else:
            terms.append(f"{c}*x**{i}")
    return " + ".join(terms).replace("+ -", "- ")


def gather_candidates(variant, n):
    """Yield candidate dicts: {points (list of [str,str]), kind, ref, note}."""
    tag = f"{variant}-n{n:02d}"

    ae = SOURCES / "alphaevolve" / f"{variant}_n{n}.txt"
    if ae.exists():
        text = ae.read_text()
        pts = points_to_strings(parse_points_text(text))
        if variant == "triangle":  # equilateral frame upstream
            pts = eq_to_right_frame(pts)
        yield {
            "points": pts,
            "kind": "alphaevolve",
            "ref": "google-deepmind/alphaevolve_results (arXiv:2506.13131)",
            "note": "converted from the equilateral frame" if variant == "triangle" else None,
        }

    if variant == "square":
        sp = SOURCES / "spiralulam" / f"config_n{n:02d}.json"
        if sp.exists():
            data = json.loads(sp.read_text())
            yield {
                "points": [[repr(float(x)), repr(float(y))] for x, y in data["points"]],
                "kind": "spiralulam",
                "ref": f"spiralulam/heilbronn config_n{n:02d}.json",
                "note": data.get("source"),
                "delta_exact": data.get("delta_exact"),
            }

    ext = SOURCES / "external" / tag
    if ext.exists():
        meta = json.loads((ext / "meta.json").read_text())
        pts = parse_points_text((ext / "coordinates.txt").read_text())
        yield {
            "points": points_to_strings(pts),
            "kind": "external",
            "ref": meta["ref"],
            "note": meta.get("note"),
            "credit": meta.get("credit"),
            "exact_coeffs": _external_exact_coeffs(ext / "exact.json"),
        }

    pap = SOURCES / "papers" / tag
    if pap.exists():
        meta = json.loads((pap / "meta.json").read_text())
        pts = parse_points_text((pap / "coordinates.txt").read_text())
        yield {
            "points": points_to_strings(pts),
            "kind": "paper",
            "ref": meta["ref"],
            "note": meta.get("note"),
        }

    rec = SOURCES / "reconstructed" / tag
    if rec.exists() and (rec / "provenance.json").exists():
        prov = json.loads((rec / "provenance.json").read_text())
        pts = parse_points_text((rec / "coordinates.txt").read_text())
        yield {
            "points": points_to_strings(pts),
            "kind": "reconstructed",
            "ref": prov.get("ref", "local reconstruction"),
            "note": prov.get("note"),
            "basis": prov.get("basis"),
        }

    exact_mod = SOURCES / "exact" / "constructions.py"
    if exact_mod.exists():
        sys.path.insert(0, str(exact_mod.parent))
        try:
            import constructions
            c = constructions.get(variant, n)
        finally:
            sys.path.pop(0)
        if c is not None:
            yield {
                "points": c["points"],
                "kind": "exact-construction",
                "ref": c.get("ref", "data/sources/exact/constructions.py"),
                "note": c.get("note"),
            }


def sticky_candidate(prev):
    """The committed canonical row as a candidate of its own, carrying the
    provenance it was built from. None when the row has no coordinates."""
    if not prev or not prev.get("points") or not prev.get("coordinates_source"):
        return None
    src = prev["coordinates_source"]
    cand = {
        "points": prev["points"],
        "kind": src.get("kind"),
        "ref": src.get("ref"),
        "note": src.get("note"),
        "basis": src.get("basis"),
        "sticky": True,
    }
    found = (prev.get("credit") or {}).get("found") or {}
    if src.get("kind") == "external" and found.get("name"):
        cand["credit"] = found["name"] + (f", {found['date']}" if found.get("date") else "")
    poly = (prev.get("value") or {}).get("exact_poly")
    if poly and poly.get("which") == "coordinate-matched":
        cand["exact_poly_prev"] = poly
    return cand


def record_window(entry):
    """Return (low, high) exact bounds implied by the ledger's recorded value,
    or None if it has none. Truncated entries ("+", lower_bound) usually mean
    value in [d, d+ulp) but were sometimes roundings (square n=7: proven
    optimum .0838590… recorded as .08386+), so accept the union of both:
    [d - ulp/2, d + ulp). Values below that are genuinely BELOW the record,
    at or above the top genuinely IMPROVE on it."""
    d = entry["decimal"]
    if d is None:
        return None
    frac = Fraction(d)
    decimals = len(d.split(".")[1]) if "." in d else 0
    ulp = Fraction(1, 10 ** decimals) if decimals else Fraction(1)
    if entry["lower_bound"]:
        return (frac - ulp / 2, frac + ulp)
    return (frac - ulp / 2, frac + ulp / 2)


def ingest():
    records = load_records()
    overrides = load_curated("overrides.json")
    changelog = load_curated("changelog.json")
    refdata = load_curated("references.json")
    refs_by_config = refdata.get("by_config", {})
    bib = refdata.get("bib", {})
    proofs = refdata.get("proofs", {})

    def proof_for(key):
        rid = proofs.get(key)
        if not rid:
            return None
        entry = bib.get(rid, {})
        return {"id": rid, "title": entry.get("title"), "url": entry.get("url")}

    audit = []
    for variant in VARIANTS:
        outdir = CANONICAL / variant
        outdir.mkdir(parents=True, exist_ok=True)
        for n in ns(variant):
            key = f"{variant}/{n}"
            entry = records.get(key)
            path = outdir / f"n{n:02d}.json"
            prev = json.loads(path.read_text()) if path.exists() else None
            best = None
            for cand in gather_candidates(variant, n):
                if variant == "triangle":
                    cand["points"] = orient_triangle_mirror(cand["points"])
                pts = [(Fraction(x), Fraction(y)) for x, y in cand["points"]]
                res = verify(variant, pts)
                if not res["feasible"]:
                    print(f"  WARN {key}: {cand['kind']} candidate infeasible, skipped",
                          file=sys.stderr)
                    continue
                if best is None or res["_value"] > best[1]["_value"]:
                    best = (cand, res)
            # Never regress (see module docstring): the committed row competes
            # too, and wins only strictly, so identical literals keep their
            # source-directory provenance.
            sticky = sticky_candidate(prev)
            if sticky is not None:
                if variant == "triangle":
                    sticky["points"] = orient_triangle_mirror(sticky["points"])
                pts = [(Fraction(x), Fraction(y)) for x, y in sticky["points"]]
                res = verify(variant, pts)
                if res["feasible"] and (best is None or res["_value"] > best[1]["_value"]):
                    print(f"  REGRESSION {key}: sources now top out at "
                          f"{fraction_to_30sig(best[1]['_value'])[:18] if best else 'nothing'} "
                          f"but the committed canonical holds "
                          f"{fraction_to_30sig(res['_value'])[:18]} ({sticky['kind']}: "
                          f"{sticky['ref']}) — keeping the canonical coordinates; a "
                          f"source directory was overwritten with a lower-valued "
                          f"configuration. Delete {path.relative_to(ROOT)} to lower "
                          f"this entry on purpose.", file=sys.stderr)
                    best = (sticky, res)

            window = record_window(entry) if entry else None
            if best is None:
                rel = "GAP"
                audit.append((key, rel, "-", entry["decimal"] if entry else "-"))
                # Still emit a coordinate-less canonical row so pages render.
                doc = canonical_doc(variant, n, entry, None, None, rel,
                                    overrides.get(key), changelog.get(key),
                                    refs_by_config.get(key), proof_for(key))
            else:
                cand, res = best
                value = res["_value"]
                if entry is None:
                    rel = "NEW"
                elif window is None:
                    rel = "OK"
                elif value < window[0]:
                    rel = "BELOW"
                elif value >= window[1]:
                    rel = "IMPROVES"
                else:
                    rel = "OK"
                audit.append((key, rel, cand["kind"],
                              fraction_to_30sig(value)[:12]))
                doc = canonical_doc(variant, n, entry, cand, res, rel,
                                    overrides.get(key), changelog.get(key),
                                    refs_by_config.get(key), proof_for(key))
            path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")

    print(f"{'row':<14}{'rel':<8}{'source':<16}value")
    for key, rel, kind, val in audit:
        if rel != "OK":
            print(f"{key:<14}{rel:<8}{kind:<16}{val}")
    counts = {}
    for _, rel, _, _ in audit:
        counts[rel] = counts.get(rel, 0) + 1
    print("audit:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return audit


def canonical_doc(variant, n, entry, cand, res, page_relation, override, changelog,
                  refs, proof=None):
    trivial = bool(entry and entry.get("trivial"))
    found = entry.get("found") if entry else None
    proved = entry.get("proved") if entry else None
    # Status describes the VALUE only; coordinate provenance (including
    # reconstruction) is a separate fact carried by coordinates_source and
    # surfaced as its own tag, never as a competing status.
    # Trivial cases are proven (the credit keeps the trivial flag, and the
    # page comments "Trivial configuration." instead of a separate badge).
    if trivial or proved:
        status = "proven"
    else:
        status = "record"

    doc = {
        "schema_version": 1,
        "variant": variant,
        "n": n,
        "frame": FRAMES[variant],
        "points": cand["points"] if cand else None,
        "value": {
            "decimal": res["value"] if res else None,
            "fraction": res["value_fraction"] if res else None,
            "exact_text": entry["exact_text"] if entry else None,
            "exact_sympy": None,
            "minimal_polynomial": None,
        },
        "status": status,
        "credit": {
            "found": found,
            "proved": proved,
            "trivial": trivial,
        },
        "proof": proof,
        "coordinates_source": ({
            "kind": cand["kind"],
            "ref": cand["ref"],
            "note": cand["note"],
            "basis": cand.get("basis"),
        } if cand else None),
        "coordinates_reconstructed": bool(cand and cand["kind"] == "reconstructed"),
        "symmetry": symmetry_record(variant, cand, entry, page_relation),
        "notes": entry["notes"] if entry else [],
        "changelog": changelog or [],
        "references": refs or [],
        "verify": res and {k: v for k, v in res.items() if k != "_value"},
    }
    # When an external submission's value improves on the recorded value (or
    # the ledger has no entry at all), the find belongs to the submitter
    # (meta.json credit), not to the holder of the superseded record. Only
    # then: within the record's window the ledger's credit is authoritative
    # (external submissions can also be exact realizations of someone else's
    # known record, e.g. square n=14). Corrections to credits go in
    # data/curated/records.json or overrides.json.
    if (cand and cand.get("kind") == "external" and cand.get("credit")
            and page_relation in ("IMPROVES", "NEW")):
        m = re.match(r"^(.+?),\s*((?:%s)\s+\d{4}|\d{4})$" % "|".join(MONTHS),
                     cand["credit"].strip())
        if m:
            doc["credit"]["found"] = {"name": m.group(1), "date": m.group(2)}
        else:
            doc["credit"]["found"] = {"name": cand["credit"].strip(), "date": None}

    if cand and cand.get("delta_exact") and not doc["value"]["exact_text"]:
        doc["value"]["exact_text"] = cand["delta_exact"]
    if override:
        deep_update(doc, override)
    # A minimal polynomial submitted alongside external coordinates applies
    # only when the curated overrides carry no exact form of their own —
    # curation always wins. finalize_exact then validates it against the
    # coordinates (45 digits, rel 1e-9) and drops it loudly on mismatch.
    if (cand and cand.get("exact_coeffs") and res is not None
            and not doc["value"].get("exact_sympy")
            and not doc["value"].get("exact_poly")):
        doc["value"]["exact_poly"] = {
            "poly": coeffs_to_poly(cand["exact_coeffs"]),
            "near": float(res["_value"]),
            "which": "coordinate-matched",
            "note": "minimal polynomial submitted with the coordinates",
        }
    elif (cand and cand.get("exact_poly_prev") and res is not None
            and not doc["value"].get("exact_sympy")
            and not doc["value"].get("exact_poly")):
        # Carried over with a sticky canonical row whose exact.json is gone.
        doc["value"]["exact_poly"] = dict(cand["exact_poly_prev"])
    finalize_exact(doc, res)
    return doc


def symmetry_record(variant, cand, entry, page_relation):
    """The symmetry group detected from the stored coordinates, plus the
    ledger's own wording when it describes this configuration. A ledger
    label is dropped once the coordinates beat the ledger's record: it
    describes the superseded configuration (square n=20 was labelled 90°
    rotational after Fable 5.1's D2 record replaced Shanley's C4 one)."""
    from .derive import detect_symmetry, symmetry_label
    reported = entry["symmetry"] if entry else None
    if page_relation in ("IMPROVES", "NEW"):
        reported = None
    if cand is None:
        return {"label": None, "reported": reported}
    pts = [(float(x), float(y)) for x, y in cand["points"]]
    sym = detect_symmetry(variant, pts)
    return {
        "group": sym["group"],
        "order": sym["order"],
        "approx": sym["approx"],
        "label": symmetry_label(sym, variant),
        "reported": reported,
    }


def finalize_exact(doc, res):
    """Evaluate a curated exact value (closed form and/or minimal polynomial)
    to 45 digits, and validate it against the exact value implied by the
    coordinates. A curated form that disagrees with the coordinates is a
    data error: it is dropped loudly rather than displayed."""
    val = doc["value"]
    if not (val.get("exact_sympy") or val.get("exact_poly")):
        return
    import mpmath
    import sympy
    mpmath.mp.dps = 60

    decs = {}
    if val.get("exact_sympy"):
        expr = sympy.sympify(val["exact_sympy"])
        decs["sympy"] = mpmath.mpf(str(sympy.N(expr, 55)))
    if val.get("exact_poly"):
        p = val["exact_poly"]
        poly = sympy.sympify(p["poly"])
        x = list(poly.free_symbols)[0]
        roots = sympy.Poly(poly, x).nroots(n=55, maxsteps=500)
        real = [sympy.re(r) for r in roots if abs(sympy.im(r)) < sympy.Float(10) ** -40]
        root = min(real, key=lambda r: abs(float(r) - p["near"]))
        decs["poly"] = mpmath.mpf(str(sympy.N(root, 55))) * p.get("scale", 1)

    vals = list(decs.values())
    if len(vals) == 2 and abs(vals[0] - vals[1]) > abs(vals[0]) * mpmath.mpf(10) ** -40:
        print(f"  WARN {doc['variant']}/{doc['n']}: exact_sympy and exact_poly disagree "
              f"({vals[0]} vs {vals[1]}) — dropping exact value", file=sys.stderr)
        val["exact_sympy"] = val["exact_poly"] = val.pop("exact_display", None) and None
        return
    exact = vals[0]

    if res is not None:
        coord = res["_value"]
        coord_mp = mpmath.mpf(coord.numerator) / mpmath.mpf(coord.denominator)
        rel = abs(coord_mp / exact - 1)
        if rel > mpmath.mpf(10) ** -9:
            print(f"  WARN {doc['variant']}/{doc['n']}: curated exact value "
                  f"{mpmath.nstr(exact, 15)} does not match coordinates "
                  f"({mpmath.nstr(coord_mp, 15)}, rel {mpmath.nstr(rel, 3)}) — dropped",
                  file=sys.stderr)
            for k in ("exact_sympy", "exact_poly", "exact_display"):
                val.pop(k, None)
            return

    val["exact_decimal"] = mpmath.nstr(exact, 45, strip_zeros=False)
    if val.get("exact_poly"):
        val["minimal_polynomial"] = val["exact_poly"]["poly"]

    # Presentation MathML, built from the curated display string so the
    # rendered form is exactly what a human would write — and re-evaluated
    # numerically so the pretty output is provably the same number.
    from .mathml import exact_to_mathml, poly_to_mathml
    if val.get("exact_display"):
        try:
            mml, parsed_value = exact_to_mathml(val["exact_display"])
            if abs(parsed_value / float(exact) - 1) > 1e-12:
                raise ValueError(f"display form evaluates to {parsed_value}, "
                                 f"exact is {mpmath.nstr(exact, 15)}")
            val["exact_mathml"] = mml
        except Exception as exc:
            print(f"  WARN {doc['variant']}/{doc['n']}: exact_display not "
                  f"renderable as MathML ({exc}) — falling back to text",
                  file=sys.stderr)
    if val.get("minimal_polynomial"):
        try:
            val["poly_mathml"] = poly_to_mathml(val["minimal_polynomial"])
        except Exception as exc:
            print(f"  WARN {doc['variant']}/{doc['n']}: polynomial not "
                  f"renderable as MathML ({exc})", file=sys.stderr)


def deep_update(doc, patch):
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(doc.get(k), dict):
            deep_update(doc[k], v)
        else:
            doc[k] = v


if __name__ == "__main__":
    ingest()
