PYTHON := python3.12
PYTHONPATH := src

.PHONY: check context data-verify evidence-verify surgedesk-verify test

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -v

context:
	$(PYTHON) scripts/validate_context.py

evidence-verify:
	$(PYTHON) scripts/build_evidence_manifest.py --verify

data-verify:
	$(PYTHON) scripts/build_banking77_workload.py >/dev/null

surgedesk-verify:
	$(PYTHON) scripts/build_surgedesk_demo.py --verify

check: context evidence-verify data-verify surgedesk-verify test
	$(PYTHON) -m compileall -q src scripts tests
