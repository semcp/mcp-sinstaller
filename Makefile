.PHONY: test run install clean

test:
	uv sync --extra dev
	uv run pytest tests/ -v

test-coverage:
	uv sync --extra dev
	uv run pytest tests/ --cov=. --cov-report=html --cov-report=term

run:
	uv run python mcp_installer.py

install:
	uv sync --extra dev

clean:
	rm -rf .pytest_cache __pycache__ tests/__pycache__ *.pyc tests/*.pyc
	rm -rf htmlcov .coverage 