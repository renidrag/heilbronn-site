"""The committed canonical rows agree with their own coordinates. Labels
copied from elsewhere go stale when a better configuration replaces a
record; these checks fail until ingest is rerun."""

import json
import pathlib

import pytest

from build.derive import detect_symmetry, symmetry_label

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = sorted((ROOT / "data" / "canonical").glob("*/n*.json"))
OVERRIDES = json.loads((ROOT / "data" / "curated" / "overrides.json").read_text())


@pytest.mark.parametrize("path", DOCS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_symmetry_matches_coordinates(path):
    doc = json.loads(path.read_text())
    sym = doc["symmetry"]
    if not doc["points"]:
        assert sym["label"] is None
        return
    pts = [(float(x), float(y)) for x, y in doc["points"]]
    det = detect_symmetry(doc["variant"], pts)
    assert (sym["group"], sym["order"], sym["approx"]) == \
        (det["group"], det["order"], det["approx"])
    assert sym["label"] == symmetry_label(det, doc["variant"])


def test_overrides_do_not_set_symmetry():
    # The group is detected from the coordinates; a curated label would
    # outlive the configuration it describes.
    assert [k for k, v in OVERRIDES.items() if "symmetry" in v] == []
