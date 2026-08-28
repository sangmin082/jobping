.PHONY: install test verify verify-all

install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

test:
	.venv/bin/pytest -q

# 예: make verify A=samsung
verify:
	.venv/bin/python scripts/verify.py $(A)

verify-all:
	.venv/bin/python scripts/verify.py --all
