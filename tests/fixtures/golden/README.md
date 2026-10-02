# Golden verifier fixtures

Point configurations with their expected `verify_output.json`.
`tests/test_verify.py` and `tests/test_verifier_js.mjs` run both verifiers
over them, the exact-rational Python one and the BigInt one in the browser,
and check that the outputs agree.

Most fixtures come from the site's own search runs and were checked by two
independent exact verifiers when they were found. They cover all three
regions and a wide range of n. Directories ending in `-live` are copies of
submissions that were the current entry when copied. Most of the rest have
since been beaten. They stay because they exercise large tie sets and
near-degenerate triangles that the current records may not.

Nothing here is read by the site build or shown on the leaderboard. It is
separate from `data/sources/` and exists only for tests.
