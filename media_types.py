# Copyright (C) 2026 Benjamin Drung <bdrung@posteo.de>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""Common functions for media types scripts."""

import csv
import pathlib
from collections.abc import Iterator

ALLOWED_MISSING_TEMPLATES = {"image/x-emf", "image/x-wmf"}
TOP_LEVEL_TYPES_CSV = "top-level-media-type-names.csv"
SKIP_TOP_LEVEL_TYPES = ("example",)


def get_top_level_media_type_names(directory: pathlib.Path) -> Iterator[str]:
    """Yield top-level media type names from the local CSV file."""
    with open(directory / TOP_LEVEL_TYPES_CSV, encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            name = row["Name"]
            if name in SKIP_TOP_LEVEL_TYPES:
                continue
            yield name
