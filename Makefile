PYTHON_FILES = $(wildcard *.py)

all: iana/top-level-media-type-names.csv

iana/top-level-media-type-names.csv:
	./download_iana_media_types.py

clean:
	rm -rf .mypy_cache __pycache__

lint: black isort mypy pylint

black:
	black -C --check --diff $(PYTHON_FILES)

isort:
	isort --check-only --diff $(PYTHON_FILES)

mypy:
	mypy --strict $(PYTHON_FILES)

pylint:
	pylint $(PYTHON_FILES)

.PHONY: black clean isort lint mypy pylint
