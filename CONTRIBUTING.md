# Contributing a configuration

Submissions are ordinary pull requests. CI checks each one in exact
rational arithmetic and posts the result on the PR. Anyone can submit,
whether the coordinates came from a person, a solver, or an automated
pipeline. The site's own search runs go through the same process.

All coordinate submissions go in `data/sources/external/`.

## What to add

Each configuration gets one directory with two required files and one
optional file:

```
data/sources/external/<variant>-nNN/
├── coordinates.txt    required: the points
├── meta.json          required: provenance, credit, page note
└── exact.json         optional: minimal polynomial of the value
```

`<variant>` is `square`, `triangle`, or `convex`. `NN` is the point count,
zero-padded: `triangle-n15`, `square-n07`. `coordinates.txt` must contain
exactly `NN` points.

A PR may add or change any number of these directories. It should not
touch anything else.

### coordinates.txt

One point per line, as two decimal numbers separated by whitespace. Lines
starting with `#` are comments.

```
# any comment you like
0.041156363310095543088824043693	0.917687273379808913822351912614
0.041156363310095543088824043693	0.041156363310095543088824043693
```

Format rules:

- Plain decimals only. No exponents or fractions, at most 6 digits before
  the point and 200 after. Each number is read as an exact rational, so the
  value that gets verified is exactly what you wrote.
- The frame depends on the variant.
  - `square`: 0 ≤ x, y ≤ 1.
  - `triangle`: the right triangle x ≥ 0, y ≥ 0, x + y ≤ 1. The site
    reports values for a unit-area triangle, so they are double the raw
    minimum area.
  - `convex`: any coordinates. The region is the convex hull of the points
    and the value is normalized by its area.
- Feasibility is checked exactly. `0.99999…` to 200 places is inside the
  square; `1.0000000001` is not. When you round, truncate toward zero. That
  keeps square coordinates inside [0, 1] and keeps x + y ≤ 1 in the
  triangle.

Use at least 15 decimal places; 30 is better. The site ranks sources by the
exact value of the numbers as written, so 30 digits of a converged optimum
beat 15 digits of the same arrangement. Ties are also detected exactly,
within a relative 1e-9 of the minimum. With fewer than about 12 decimals,
triangles that should tie fall outside that window and the figure shows
fewer minimal triangles than the configuration really has. The checker
warns when this is likely.

### meta.json

```json
{
 "ref": "where these coordinates come from (paper, repo, pipeline run)",
 "credit": "Your Name, August 2026",
 "note": "anything the configuration page should say about them"
}
```

`ref` is required (up to 300 characters). `credit` (up to 300) and `note`
(up to 2000) are optional but help readers.

- Write `credit` as `"Human Name, Month YYYY"`. If the submission beats
  the current record, this string becomes the **Found by** line on the
  entry, so give a person's name rather than a bot or account name.
- `note` appears verbatim in the provenance section of the configuration
  page. One or two sentences on the method is usually right.

### exact.json (optional)

If you know the exact value, give its minimal polynomial as a list of
integer coefficients, constant term first. The polynomial is for the
normalized value A that the site reports.

```json
{
 "minimal_polynomial": [-4, -13, 5438, 161469, 1609650, 5250987]
}
```

This is the triangle n = 15 value:
5250987A⁵ + 1609650A⁴ + 161469A³ + 5438A² − 13A − 4. Coefficients too large
for 64-bit integers can be written as strings of digits. Expressions are
not accepted.

The checker confirms, in exact arithmetic, that the polynomial has a root
within a relative 1e-9 of the value your coordinates give. It does not
check that the polynomial is irreducible, so verify that yourself. If your
submission becomes the entry, the build checks the polynomial again and
shows it on the page.

## What happens on the PR

A workflow runs the site's exact verifier on every changed directory,
checking all C(n, 3) triangles in rational arithmetic. It then comments
with the exact value, the tie structure, the detected symmetry, and a
comparison against the current entry. The check fails if the file is
malformed, a point is outside the region, the point count is wrong, or the
polynomial does not match. Read the comment, fix the problem, and push to
the same branch.

The value rules:

- A new directory that verifies is accepted even if it scores below the
  current entry. That is useful when, for example, you have the original
  author's coordinates for an entry the site only has as a reconstruction.
  Say so in the `note`.
- A change to an existing directory must not lower that directory's value.
  An equal value is fine (editing `meta.json`, adding digits, adding
  `exact.json`). A lower one is refused and needs a reviewed PR.

Once the check passes and the PR is merged, the site picks the
highest-valued source for each entry and rebuilds. Your configuration is
live within about ten minutes.

An entry's value never goes down on merge. The PR check compares against
`main` as of when it ran. If something better lands before your PR merges,
the build keeps the better coordinates and logs the conflict. Rebase and
rerun the check if you think yours still wins.

## Checklist for automated agents

1. Add one directory per configuration under `data/sources/external/`,
   named `<variant>-nNN`. Do not touch any other path.
2. `coordinates.txt`: exactly NN points, plain decimals, 30 decimal places,
   truncated toward zero. Check feasibility in exact arithmetic before
   opening the PR.
3. `meta.json`: `ref` is required. `credit` is `"Human Name, Month YYYY"`.
   `note` is one informative sentence.
4. Include `exact.json` only if you have checked the polynomial yourself.
5. Run the check CI will run:
   `python3 scripts/check_submission.py data/sources/external/<dir>`.
6. After opening the PR, read the verification comment. If it failed, fix
   and push to the same branch.

## Notes, corrections, references

Corrections to credits, history, or notes don't need coordinates. Open a PR
against `data/curated/` (`overrides.json`, `changelog.json`,
`references.json`) following the shape of the existing entries. These are
reviewed by hand.

## Checking locally

```
make check-submission DIRS=data/sources/external/<variant>-nNN
make test
```
