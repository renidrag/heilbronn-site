PY := .venv/bin/python

.PHONY: build test serve sync-sources clean check-submission check-links

build:
	$(PY) -m build

test:
	$(PY) -m pytest tests/ -q
	node --test tests/test_verifier_js.mjs

serve:
	$(PY) -m http.server -d dist 8080

sync-sources:
	$(PY) build/sync_sources.py

# Verify a coordinate submission the same way the PR workflow does:
#   make check-submission DIRS=data/sources/external/square-n17
check-submission:
	python3 scripts/check_submission.py $(DIRS)

# Every external link on the built site; run weekly in CI.
check-links:
	$(PY) scripts/check_external_links.py

clean:
	rm -rf dist
