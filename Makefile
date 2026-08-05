PYTHON_FILES = $(wildcard *.py)

all: iana/top-level-media-type-names.csv iana.csv

iana/top-level-media-type-names.csv:
	./download_iana_media_types.py

iana.csv: iana/top-level-media-type-names.csv $(wildcard iana/*.csv) $(wildcard parser/file_extensions/*)
	./generate_iana_csv.py

check:
	python3 -m unittest -v $(PYTHON_FILES)

clean:
	rm -f iana.csv
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

.PHONY: black check clean isort lint mypy pylint
