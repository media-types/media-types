ifdef EXTRA_MEDIA_TYPES
ENHANCE_IANA_CSV_ARGS += --input=iana.csv --input=$(EXTRA_MEDIA_TYPES)
endif
ifdef EXTRA_FILE_EXTENSIONS
ENHANCE_IANA_CSV_ARGS += --extra-file-extensions=$(EXTRA_FILE_EXTENSIONS)
endif
ifdef EXTRA_KNOWN_DUPLICATES
ENHANCE_IANA_CSV_ARGS += --known-duplicates=enhancement/duplicates.txt --known-duplicates=$(EXTRA_KNOWN_DUPLICATES)
endif
ifdef EXTRA_PRIMARY_FILE_EXTENSIONS
ENHANCE_IANA_CSV_ARGS += --primary-file-extensions=enhancement/primary-file-extensions.csv --primary-file-extensions=$(EXTRA_PRIMARY_FILE_EXTENSIONS)
endif

ifdef EXTRA_EXCLUDE
GENERATE_MIME_TYPES_ARGS += --exclude=mime_types/exclude.csv --exclude=$(EXTRA_EXCLUDE)
endif
ifdef HEADER
GENERATE_MIME_TYPES_ARGS += --header=$(HEADER)
endif
ifdef FOOTER
GENERATE_MIME_TYPES_ARGS += --footer=$(FOOTER)
endif

NAME = media-types
# Use YYYY.0M.0D defined in https://calver.org/
VERSION = 2026.08.21
PREFIX = /usr
DATADIR = $(PREFIX)/share/media-types
PYTHON_FILES = $(wildcard scripts/*.py)

all: iana/top-level-media-type-names.csv media-types.csv mime.types

iana/top-level-media-type-names.csv:
	scripts/download_iana_media_types.py

iana.csv: iana/top-level-media-type-names.csv $(wildcard iana/*.csv) $(wildcard parser/file_extensions/*)
	scripts/generate_iana_csv.py

media-types.csv: iana.csv $(wildcard enhancement/*)
	scripts/enhance_iana_csv.py $(ENHANCE_IANA_CSV_ARGS)

mime.types: media-types.csv $(wildcard mime_types/*)
	scripts/generate_mime_types.py $(GENERATE_MIME_TYPES_ARGS)

install: media-types.csv mime.types
	install -m 755 -d $(DESTDIR)/etc $(DESTDIR)$(DATADIR)
	install -m 644 mime.types $(DESTDIR)/etc/mime.types
	install -m 644 media-types.csv $(DESTDIR)$(DATADIR)/media-types.csv

check:
	python3 -m unittest discover -p '*.py' -s scripts -v

clean:
	rm -f iana.csv media-types.csv mime.types
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

_site/index.html: $(wildcard website/*.jinja2) iana.csv media-types.csv mime.types
	scripts/generate_website.py

_site/%: %
	@mkdir -p _site
	cp $< $@

_site/%/: iana/%/
	mkdir -p $@
	for f in $<*; do cp "$$f" "_site/$${f#iana/}.txt"; done

site: _site/index.html _site/iana.csv _site/media-types.csv _site/mime.types $(patsubst iana/%,_site/%,$(wildcard iana/*/))

%.asc: %
	gpg --armor --batch --detach-sign --yes --output $@ $^

%.tar.xz: .git
	git archive --prefix=$(NAME)-$(VERSION)/ HEAD | xz -c -9 -T1 > $@

dist: ../$(NAME)-$(VERSION).tar.xz ../$(NAME)-$(VERSION).tar.xz.asc

version:
	@echo $(VERSION)

.PHONY: black check clean install isort lint mypy pylint site version
