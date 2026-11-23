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

"""Convert an enhanced IANA CSV into a nginx types config file."""

import argparse
import logging
import pathlib
import sys
from collections.abc import Iterable

from media_types import (
    EnhancedMediaType,
    EnhancedMediaTypeList,
    check_unused_excludes,
    read_exclude_list_from_csvs,
)

DEFAULT_EXCLUDE = pathlib.Path("nginx_types/exclude.csv")
LOG_FORMAT = "%(name)s %(levelname)s: %(message)s"


def write_nginx_mime_types(
    path: pathlib.Path, mime_types: Iterable[EnhancedMediaType]
) -> None:
    """Writes media types with file extensions to a text file."""
    with path.open("w", encoding="utf-8") as mime_types_file:
        mime_types_file.write("types {\n")
        for mime_type in mime_types:
            if not mime_type.primary_file_extensions:
                continue
            mime_types_file.write(
                f"  {mime_type.template.lower()}"
                f"  {' '.join(mime_type.primary_file_extensions)};\n"
            )
        mime_types_file.write("}\n")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-i",
        "--input",
        default=pathlib.Path("media-types.csv"),
        type=pathlib.Path,
        help="Input enhanced IANA CSV file including primary file extensions column"
        " (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=pathlib.Path("nginx.types"),
        type=pathlib.Path,
        help="Output nginx mime.types file (default: %(default)s)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        type=pathlib.Path,
        help=f"CSV file listing media types to exclude."
        f" Can be specified multiple times. (default: {DEFAULT_EXCLUDE})",
    )
    args = parser.parse_args()
    if args.exclude is None:
        args.exclude = [DEFAULT_EXCLUDE]
    return args


def main() -> int:
    """Convert one or more enhanced IANA CSVs into a nginx mime.types file."""
    args = parse_args()
    logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)

    media_types = EnhancedMediaTypeList.from_files([args.input])
    exclude, failures = read_exclude_list_from_csvs(args.exclude)

    removed = media_types.remove_templates(set(exclude))
    failures += check_unused_excludes(exclude, set(removed))
    write_nginx_mime_types(args.output, media_types)
    return failures


if __name__ == "__main__":
    sys.exit(main())
