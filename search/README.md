# Search toolkit

The tools behind the site's own record runs. They were written in a
separate companion repository, since retired, and copied here so that
everything on the site can be found, polished, and verified from this repo
alone.

- `attack.py`: basin hopping (perturb, polish locally, keep the best)
- `fastheil.py`, `heil.py`: fast objective evaluation and core geometry
- `search.py`, `ladder.py`, `grow.py`, `mirror.py`: search strategies
  (cold starts, laddering from n to n+1, symmetric seeds)
- `refine.py`, `sym.py`: trust-region SLP polishing, KKT tightening,
  symmetry detection and symmetric restriction
- `consensus.py`, `CONSENSUS_NOTES.md`: cross-checking independent runs
- `alphaevolve_extract.py`: importing configurations from AlphaEvolve runs
- `verify_a.py`, `verify_b.py`: two independent exact verifiers. The
  build's verifier is a library version of `verify_a.py`.
- `render.py`, `gifseed.py`: figures and seeds for reconstruction

The reconstruction pipeline built on these lives in `reconstruct/` at the
repo root.
