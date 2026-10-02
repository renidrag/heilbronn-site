"""Symbolic/trivial configurations emitted as 30-decimal literals.

Only configurations whose exact description is beyond doubt live here:
the trivial small-n cases and the regular polygons for the convex variant.
Everything else that lacks published coordinates goes through the
reconstruction pipeline instead.
"""

import mpmath

mpmath.mp.dps = 40


def _fmt(x):
    # 30-decimal fixed point, truncated toward zero (the convex value is
    # scale/position invariant, so truncation is harmless).
    f = mpmath.mpf(x)
    scaled = int(mpmath.floor(abs(f) * mpmath.mpf(10) ** 30))
    sign = "-" if f < 0 and scaled != 0 else ""
    return f"{sign}{scaled // 10**30}.{scaled % 10**30:030d}"


def regular_polygon(m):
    pts = []
    for j in range(m):
        th = 2 * mpmath.pi * j / m + mpmath.pi / 2
        pts.append([_fmt(mpmath.cos(th)), _fmt(mpmath.sin(th))])
    return pts


CONSTRUCTIONS = {
    ("triangle", 3): {
        "points": [["0", "0"], ["1", "0"], ["0", "1"]],
        "note": "the container's vertices",
    },
    ("triangle", 4): {
        "points": [["0", "0"], ["1", "0"], ["0", "1"],
                   ["0.333333333333333333333333333333",
                    "0.333333333333333333333333333333"]],
        "note": "vertices plus centroid",
    },
    ("triangle", 8): {
        # Exact realization of the certified optimum (Sudermann-Merx 2026,
        # arXiv:2607.15021): the 11-triangle tie system solved to 400
        # digits, each coordinate identified as an explicit degree-7
        # algebraic number (see triangle-n08-coordinate-minpolys.json).
        # 2*min-area equals the certified septic root exactly.
        "points": [
            ["0.888607734966284163841259909257", "0.111392265033715836158740090743"],
            ["0.111999705654029949029324356726", "0"],
            ["0.720562726018855112355721845127", "0"],
            ["0.439307097839209917412298611307", "0.484405907813650743134099078538"],
            ["0.395276367904074664542156913136", "0.212129872844956775236907723322"],
            ["0", "0.155433665397645381124515838859"],
            ["0.111999705654029949029324356726", "0.605262423310288723455274536510"],
            ["0", "1"],
        ],
        "note": "exact realization of the certified optimum: each coordinate an explicit degree-7 algebraic number, identified here from the tie system (minimal polynomials in data/sources/exact/triangle-n08-coordinate-minpolys.json)",
    },
    ("triangle", 9): {
        # The reconstruction converged to exact rationals: every coordinate
        # is a multiple of 1/56 and the value is exactly 43/784 = 43/28².
        # A Goldberg-style grid configuration (Cantrell's arrangement).
        "points": [
            ["0.875", "0.125"], ["0", "0.875"], ["0.125", "0"],
            ["0", "0.107142857142857142857142857142"],
            ["0.892857142857142857142857142857", "0"],
            ["0.107142857142857142857142857142", "0.892857142857142857142857142857"],
            ["0.178571428571428571428571428571", "0.392857142857142857142857142857"],
            ["0.428571428571428571428571428571", "0.178571428571428571428571428571"],
            ["0.392857142857142857142857142857", "0.428571428571428571428571428571"],
        ],
        "note": "exact rational configuration on a 1/56 grid, value exactly 43/784; identified here from the reconstruction's convergence",
    },
    ("convex", 3): {"points": regular_polygon(3), "note": "any triangle"},
    ("convex", 7): {
        # Derived exactly on this site from the tie structure of the proven
        # optimum (Yang–Zeng 1995, value exactly 1/9): the optimal
        # configurations form a one-parameter family — center + two
        # equilateral-triangle orbits 30° apart with radius ratio
        # s ∈ [√3/2, 2/√3], every member achieving exactly 1/9. This is the
        # s = 2/√3 endpoint member (9 minimal triangles), matching the
        # published figure. Coordinates: (0,1), (±√3/2, −1/2),
        # (−1/√3, ±1), (2/√3, 0), and the center.
        "points": [
            ["0", "1"],
            ["-0.866025403784438646763723170752", "-0.5"],
            ["0.866025403784438646763723170752", "-0.5"],
            ["-0.577350269189625764509148780501", "1"],
            ["-0.577350269189625764509148780501", "-1"],
            ["1.154700538379251529018297561003", "0"],
            ["0", "0"],
        ],
        "note": ("one member (s = 2/√3, matching the published figure) of the "
                 "one-parameter optimal family derived here: center + two "
                 "equilateral-triangle orbits 30° apart, radius ratio "
                 "s ∈ [√3/2, 2/√3], all achieving exactly 1/9"),
    },
    ("convex", 4): {"points": regular_polygon(4), "note": "square (any parallelogram)"},
    ("convex", 5): {"points": regular_polygon(5), "note": "regular pentagon"},
    ("convex", 6): {"points": regular_polygon(6), "note": "regular hexagon"},
}


def get(variant, n):
    c = CONSTRUCTIONS.get((variant, n))
    if c is None:
        return None
    return {"points": c["points"], "note": c["note"],
            "ref": "data/sources/exact/constructions.py"}
