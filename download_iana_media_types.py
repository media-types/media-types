#!/usr/bin/python3

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

"""Download and update IANA media type CSV assignments and templates."""

import argparse
import csv
import logging
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator, Sequence

from media_types import (
    ALLOWED_MISSING_TEMPLATES,
    TOP_LEVEL_TYPES_CSV,
    get_top_level_media_type_names,
)

BASE_URL = "https://www.iana.org/assignments"
MEDIA_TYPES_URL = f"{BASE_URL}/media-types"
EXPECT_MISSING = {f"{MEDIA_TYPES_URL}/{t}" for t in ALLOWED_MISSING_TEMPLATES}
LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s: %(message)s"
__script_name__ = os.path.basename(sys.argv[0]) if __name__ == "__main__" else __name__


def _strip_trailing_whitespace(text: str) -> str:
    stripped = "\n".join(l.rstrip() for l in text.splitlines())
    return stripped.rstrip() + os.linesep


def download_file(url: str, path: pathlib.Path) -> int:
    """Download a file from a URL and save it if the content has changed.

    Return failure count."""
    request = urllib.request.Request(url)
    try:
        previous_content = path.read_text("utf-8")
    except FileNotFoundError:
        previous_content = ""
    try:
        with urllib.request.urlopen(request) as response:
            encoding = response.headers.get_content_charset() or "utf-8"
            content = _strip_trailing_whitespace(response.read().decode(encoding))
        if content != previous_content:
            path.parent.mkdir(exist_ok=True)
            path.write_text(content, "utf-8")
            logger = logging.getLogger(__script_name__)
            logger.info("Updated content for '%s' (%d bytes).", path, len(content))
    except urllib.error.HTTPError as error:
        logger = logging.getLogger(__script_name__)
        if url in EXPECT_MISSING and error.code == 404:
            logger.info("As expected '%s' was not found.", url)
        else:
            logger.error(
                "Failed to download '%s': HTTP %s (%s)", url, error.code, error.reason
            )
            return 1
    except urllib.error.URLError as error:
        logger = logging.getLogger(__script_name__)
        logger.error("Network error while downloading '%s': %s", path, error.reason)
        return 1
    except OSError as error:
        logger = logging.getLogger(__script_name__)
        logger.error("File system error writing to '%s': %s", path, error)
        return 1
    return 0


def download_media_types(
    top_level_media_type_names: Sequence[str], directory: pathlib.Path
) -> int:
    """Download media type CSV files for each specified top-level media type."""
    logger = logging.getLogger(__script_name__)
    logger.info(
        "Downloading %i media type CSV files...", len(top_level_media_type_names)
    )
    failures = 0
    for media_type in top_level_media_type_names:
        url = f"{MEDIA_TYPES_URL}/{media_type}.csv"
        path = directory / f"{media_type}.csv"
        failures += download_file(url, path)
    return failures


def download_templates_from_file(
    media_type_file: pathlib.Path, directory: pathlib.Path
) -> int:
    """Download all media type template files listed inside a given media type CSV."""
    logger = logging.getLogger(__script_name__)
    templates = list(read_templates(media_type_file))
    logger.info(
        "Downloading %i media type template files for %s...",
        len(templates),
        media_type_file,
    )
    failures = 0
    for template in templates:
        url = f"{MEDIA_TYPES_URL}/{template}"
        path = directory / template
        failures += download_file(url, path)
    return failures


def download_templates(
    top_level_media_type_names: Iterable[str], directory: pathlib.Path
) -> int:
    """Download template files for all provided top-level media types."""
    failures = 0
    for media_type in top_level_media_type_names:
        failures += download_templates_from_file(
            directory / f"{media_type}.csv", directory
        )
    return failures


def download_top_level_media_type_names(directory: pathlib.Path) -> int:
    """Download the main top-level media types CSV file from IANA."""
    logger = logging.getLogger(__script_name__)
    logger.info("Downloading top-level media types CSV...")
    url = f"{BASE_URL}/top-level-media-types/{TOP_LEVEL_TYPES_CSV}"
    path = directory / TOP_LEVEL_TYPES_CSV
    return download_file(url, path)


def read_templates(path: pathlib.Path) -> Iterator[str]:
    """Read a media type CSV file and yield template file relative paths."""
    with open(path, encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            yield row["Template"]


def main() -> int:
    """Parse CLI arguments and download IANA media type definitions and templates."""
    start_time = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-d",
        "--directory",
        default=pathlib.Path("iana"),
        type=pathlib.Path,
        help="directory to store downloaded IANA files (default: %(default)s)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        dest="log_level",
        action="store_const",
        const=logging.ERROR,
        default=logging.INFO,
        help="Do not write anything to standard error except errors.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format=LOG_FORMAT)
    logger = logging.getLogger(__script_name__)

    failures = 0
    failures += download_top_level_media_type_names(args.directory)
    top_level_media_type_names = list(get_top_level_media_type_names(args.directory))
    failures += download_media_types(top_level_media_type_names, args.directory)
    failures += download_templates(top_level_media_type_names, args.directory)

    elapsed_time = time.perf_counter() - start_time
    logger.info("Completed execution in %.2f seconds.", elapsed_time)
    return failures


if __name__ == "__main__":
    sys.exit(main())
