# heilbronn-site

Record tables for the Heilbronn triangle problem, live at
<https://math.tejstead.com/heilbronn>.

The problem: put n points in a region of unit area so that the smallest
triangle with vertices among them is as large as possible. The site covers
the square, the triangle, and convex regions for n = 3 to 36. Each entry
has exact coordinates, a closed form or minimal polynomial when one is
known, its symmetry and tie structure drawn on the figure, and links to any
optimality proof. A verifier runs in the browser so you can check a
configuration yourself.

The tables continue Erich Friedman's Packing Center, which went offline in
2026.

If you have a better configuration or an exact value for an existing one,
open a pull request; [CONTRIBUTING.md](CONTRIBUTING.md) has the format. CI
verifies the coordinates in exact arithmetic and the entry goes live a few
minutes after merge.

New records are announced in an Atom feed,
<https://math.tejstead.com/heilbronn/records.xml>.

## Layout

| Path | Contents |
| --- | --- |
| `data/sources/` | Coordinate sources, each directory with its own `ATTRIBUTION.md`. `external/` is where submissions go. |
| `data/curated/` | The record ledger (`records.json`), references, overrides, changelog. |
| `data/canonical/` | One JSON per configuration, generated from the sources. |
| `build/` | The site generator. |
| `search/` | The search toolkit behind the site's own records. |
| `reconstruct/` | Optimization that recovers configurations whose coordinates were never published. |
| `proofs/` | Formal proofs and snapshots for external verifiers. |
| `scripts/` | The submission checker and import helpers. |
| `templates/`, `assets/` | Jinja2 templates, CSS, JavaScript. |
| `tests/` | pytest and node golden tests for the two verifiers. |

## Building locally

```
make build   # build the full site into dist/
make test    # run the verifier tests
make serve   # preview on :8080
```

## Data provenance

Historical values, credits, and symmetry labels were copied from the
Packing Center before it went offline. They live in
`data/curated/records.json` and are maintained by hand. Every figure is
drawn from coordinates; none of Friedman's images are reused.

Coordinates come from:

- community submissions and the site's own search runs (`data/sources/external/`)
- [spiralulam/heilbronn](https://github.com/spiralulam/heilbronn) (MIT)
- [google-deepmind/alphaevolve_results](https://github.com/google-deepmind/alphaevolve_results)
- exact constructions from the literature
- local reconstruction, which the entry's page labels as such

## License

The code is [MIT](LICENSE). Data under `data/sources/` carries its own
attribution in the `ATTRIBUTION.md` beside it.
