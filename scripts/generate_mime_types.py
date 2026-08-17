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

"""Convert an enhanced IANA CSV into a mime.types file.

The mime.types file is a text file containing media types with tab-aligned
file extensions.
"""

import argparse
import logging
import math
import os
import pathlib
import sys
from collections.abc import Iterable

from media_types import EnhancedMediaType, EnhancedMediaTypeList, iter_csv_rows

DEFAULT_EXCLUDE = pathlib.Path("mime_types/exclude.csv")
MIME_TYPE_WIDTH = 48
TAB_WIDTH = 8
LOG_FORMAT = "%(name)s %(levelname)s: %(message)s"
__script_name__ = os.path.basename(sys.argv[0]) if __name__ == "__main__" else __name__


def check_unused_excludes(excludes: Iterable[str], removed: set[str]) -> int:
    """Check that all excludes where used."""
    failures = 0

    unused = [media_type for media_type in excludes if media_type not in removed]
    if unused:
        logger = logging.getLogger(__script_name__)
        logger.warning("%i unused excludes: %s", len(unused), unused)
        failures += 1

    return failures


def read_exclude_list_from_csvs(paths: Iterable[pathlib.Path]) -> tuple[list[str], int]:
    """Read CSV files to compile a unique set of media types to exclude."""
    exclude = []
    failures = 0
    for path in paths:
        for row in iter_csv_rows(path):
            media_type = row["Media Type"]
            if media_type in exclude:
                logger = logging.getLogger(__script_name__)
                logger.warning("Duplicate media type in removal list: %s", media_type)
                failures += 1
                continue
            exclude.append(media_type)
    return exclude, failures


def write_mime_types(
    path: pathlib.Path,
    mime_types: Iterable[EnhancedMediaType],
    header: str,
    footer: str,
) -> None:
    """Writes media types with tab-aligned file extensions to a text file."""
    with path.open("w", encoding="utf-8") as mime_types_file:
        mime_types_file.write(header)
        for mime_type in mime_types:
            if mime_type.unique_file_extensions:
                num_tabs = max(
                    1,
                    math.ceil((MIME_TYPE_WIDTH - len(mime_type.template)) / TAB_WIDTH),
                )
                mime_types_file.write(
                    f"{mime_type.template}{'\t' * num_tabs}"
                    f"{' '.join(mime_type.unique_file_extensions)}\n"
                )
            else:
                mime_types_file.write(f"{mime_type.template}\n")
        mime_types_file.write(footer)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-i",
        "--input",
        default=pathlib.Path("media-types.csv"),
        type=pathlib.Path,
        help="Input enhanced IANA CSV file including unique file extensions column"
        " (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=pathlib.Path("mime.types"),
        type=pathlib.Path,
        help="Output mime.types file (default: %(default)s)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        type=pathlib.Path,
        help=f"CSV file listing media types to exclude."
        f" Can be specified multiple times. (default: {DEFAULT_EXCLUDE})",
    )
    parser.add_argument(
        "--header",
        default=pathlib.Path("mime_types/header.txt"),
        type=pathlib.Path,
        help="File containing a header to add to the generated mime.types file"
        " (default: %(default)s)",
    )
    parser.add_argument(
        "--footer",
        type=pathlib.Path,
        help="File containing a footer to add to the generated mime.types file"
        " (default: none)",
    )

    args = parser.parse_args()
    if args.exclude is None:
        args.exclude = [DEFAULT_EXCLUDE]
    return args


def main() -> int:
    """Convert one or more enhanced IANA CSVs into a mime.types file."""
    args = parse_args()
    logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)

    media_types = EnhancedMediaTypeList.from_files([args.input])
    exclude, failures = read_exclude_list_from_csvs(args.exclude)
    header = args.header.read_text("utf-8")
    footer = args.footer.read_text("utf-8") if args.footer else ""

    removed = media_types.remove_templates(set(exclude))
    failures += check_unused_excludes(exclude, set(removed))
    write_mime_types(args.output, media_types, header, footer)
    return failures


if __name__ == "__main__":
    sys.exit(main())
