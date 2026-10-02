# Formal proofs

Source-only snapshots of formalizations. Projects prepared for the Palomar
registry go in `proofs/palomar/<project-name>/`.

A Palomar submission is pinned by three things: this repository, a full
40-character commit SHA, and the path to the project's `comparator.json`.
The reviewed source stays fixed even as `main` moves on.

Only source, verifier metadata, and human-readable verification notes are
kept here. Build output and caches (`.lake/`, `.olean`, `.ilean`) are left
out. The repository's [MIT license](../LICENSE) covers these projects.
