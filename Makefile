.PHONY: install-dev test

install-dev:
	python3 -m pip install -r requirements-dev.txt

test:
	python3 -m pytest tests -q
