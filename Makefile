ifdef EXTRA_MEDIA_TYPES
ENHANCE_IANA_CSV_ARGS += --input=iana.csv --input=$(EXTRA_MEDIA_TYPES)
endif
ifdef EXTRA_FILE_EXTENSIONS
ENHANCE_IANA_CSV_ARGS += --extra-file-extensions=$(EXTRA_FILE_EXTENSIONS)
endif
ifdef EXTRA_KNOWN_DUPLICATES
ENHANCE_IANA_CSV_ARGS += --known-duplicates=enhancement/duplicates.txt --known-duplicates=$(EXTRA_KNOWN_DUPLICATES)
endif
ifdef EXTRA_UNIQUE_FILE_EXTENSIONS
ENHANCE_IANA_CSV_ARGS += --unique-file-extensions=enhancement/unique-file-extensions.csv --unique-file-extensions=$(EXTRA_UNIQUE_FILE_EXTENSIONS)
endif

PYTHON_FILES = $(wildcard *.py)

all: iana/top-level-media-type-names.csv enhanced.csv

iana/top-level-media-type-names.csv:
	./download_iana_media_types.py

iana.csv: iana/top-level-media-type-names.csv $(wildcard iana/*.csv) $(wildcard parser/file_extensions/*)
	./generate_iana_csv.py

enhanced.csv: iana.csv $(wildcard enhancement/*)
	./enhance_iana_csv.py $(ENHANCE_IANA_CSV_ARGS)

check:
	python3 -m unittest -v $(PYTHON_FILES)

clean:
	rm -f enhanced.csv iana.csv
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

_site/index.html: website/index.html.jinja2 iana.csv enhanced.csv
	./generate_index.py

_site/%.csv: %.csv
	@mkdir -p _site
	cp $< $@

_site/%/: iana/%/
	mkdir -p $@
	for f in $<*; do cp "$$f" "_site/$${f#iana/}.txt"; done

site: _site/index.html _site/iana.csv $(patsubst iana/%,_site/%,$(wildcard iana/*/))

.PHONY: black check clean isort lint mypy pylint site
