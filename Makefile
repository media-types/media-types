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
	rm -rf .mypy_cache __pycache__ _site

lint: black isort mypy pylint

black:
	black -C --check --diff $(PYTHON_FILES)

isort:
	isort --check-only --diff $(PYTHON_FILES)

mypy:
	mypy --strict $(PYTHON_FILES)

pylint:
	pylint $(PYTHON_FILES)

_site/index.html: website/index.html.jinja2 iana.csv
	./generate_index.py

_site/%.csv: %.csv
	@mkdir -p _site
	cp $< $@

_site/%/: iana/%/
	mkdir -p $@
	for f in $<*; do cp "$$f" "_site/$${f#iana/}.txt"; done

site: _site/index.html _site/iana.csv $(patsubst iana/%,_site/%,$(wildcard iana/*/))

.PHONY: black check clean isort lint mypy pylint site
