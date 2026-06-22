.PHONY: install dev test lint clean run

VERSION = 0.2.0

install:
	pip install -r requirements/base.txt

dev:
	pip install -e ".[dev]"

all:
	pip install -e ".[all]"

test:
	python -m pytest tests/ -v --tb=short

test-cov:
	python -m pytest tests/ --cov=meetguard --cov-report=term-missing

lint:
	ruff check meetguard/
	black --check meetguard/ tests/

format:
	black meetguard/ tests/

typecheck:
	mypy meetguard/ --ignore-missing-imports

run:
	python -m meetguard.main

run-headless:
	python -m meetguard.main --headless

dry-run:
	python -m meetguard.main --dry-run

enroll:
	python scripts/enroll_executive.py

models:
	python scripts/download_models.py

setup-audio:
	python -m meetguard.main --setup-audio

list-devices:
	python -m meetguard.main --list-audio-devices

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache *.egg-info dist build
	find . -name "*.pyc" -delete

version:
	@echo MeetGuard AI v$(VERSION)
