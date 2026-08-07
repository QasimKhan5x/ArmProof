PYTHON := python3.12
PYTHONPATH := src

.PHONY: check data-verify evidence-verify surgedesk-verify test

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -v

evidence-verify:
	$(PYTHON) scripts/build_evidence_manifest.py --verify

data-verify:
	$(PYTHON) scripts/build_banking77_workload.py --verify >/dev/null

surgedesk-verify:
	$(PYTHON) scripts/build_surgedesk.py --verify

check: evidence-verify data-verify surgedesk-verify test
	$(PYTHON) -m compileall -q src scripts tests
