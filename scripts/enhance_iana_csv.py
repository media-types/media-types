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

"""Enhance IANA CSV with primary file extensions."""

import argparse
import collections
import logging
import os
import pathlib
import sys
from collections.abc import Collection, Iterable, Iterator, Mapping
from typing import Any

from media_types import (
    EnhancedMediaType,
    EnhancedMediaTypeList,
    MediaType,
    MediaTypeList,
    iter_csv_rows,
    iter_non_comment_lines,
    parse_space_separated_list,
)

DEFAULT_INPUT = pathlib.Path("iana.csv")
DEFAULT_KNOWN_DUPLICATES = pathlib.Path("enhancement/duplicates.txt")
DEFAULT_PRIMARY_FILE_EXTENSIONS = pathlib.Path(
    "enhancement/primary-file-extensions.csv"
)
LOG_FORMAT = "%(name)s %(levelname)s: %(message)s"
__script_name__ = os.path.basename(sys.argv[0]) if __name__ == "__main__" else __name__


def read_mapping_from_csv(
    paths: Iterable[pathlib.Path], key_name: str, value_name: str
) -> tuple[dict[str, str], int]:
    """Read CSV files and return a dictionary from two columns."""
    logger = logging.getLogger(__script_name__)
    mapping: dict[str, str] = {}
    failures = 0
    for path in paths:
        duplicates = set()
        for row in iter_csv_rows(path):
            key = row[key_name]
            value = row[value_name]
            if key in mapping:
                logger.info(
                    "Updating %s '%s' from '%s' to '%s'.",
                    key_name.lower(),
                    key,
                    mapping[key],
                    value,
                )
            if key in duplicates:
                logger = logging.getLogger(__script_name__)
                logger.warning(
                    "Duplicate %s entry in %s: %s", key_name.lower(), path, key
                )
                failures += 1
            mapping[key] = value
            duplicates.add(key)
    return mapping, failures


def read_extra_file_extensions_mapping(
    paths: Iterable[pathlib.Path],
) -> tuple[dict[str, list[str]], int]:
    """Read template-to-extension mappings from CSV files."""
    mapping, failures = read_mapping_from_csv(paths, "Template", "File Extensions")
    return {k: parse_space_separated_list(v) for k, v in mapping.items()}, failures


def enhance_media_types(
    media_types: Iterable[MediaType],
    duplicates: Collection[str],
    lowercase: Collection[str],
    primary_file_extension_mapping: Mapping[str, str],
) -> tuple[EnhancedMediaTypeList, int]:
    """Enhance media types by filtering and resolving file extensions."""
    enhanced = EnhancedMediaTypeList()
    failures = 0
    used_extensions = set()
    checked_extensions = set()
    for media_type in media_types:
        primary_file_extensions = []
        for extension in media_type.get_lowercased_file_extensions(lowercase):
            primary_type = primary_file_extension_mapping.get(extension)
            if primary_type is not None:
                checked_extensions.add(extension)
                if primary_type == media_type.template:
                    primary_file_extensions.append(extension)
                    used_extensions.add(extension)
            elif extension not in duplicates:
                primary_file_extensions.append(extension)
        enhanced.append(
            EnhancedMediaType.from_media_type(media_type, primary_file_extensions)
        )

    unchecked = {
        k: v
        for k, v in primary_file_extension_mapping.items()
        if k not in checked_extensions
    }
    if unchecked:
        logger = logging.getLogger(__script_name__)
        logger.warning(
            "%i completely unused primary file extension mappings: %s",
            len(unchecked),
            unchecked,
        )
        failures += 1

    unused = {
        k: v
        for k, v in primary_file_extension_mapping.items()
        if k not in used_extensions and v and k not in unchecked
    }
    if unused:
        logger = logging.getLogger(__script_name__)
        logger.warning(
            "%i unused primary file extension mappings: %s", len(unused), unused
        )
        failures += 1

    return enhanced, failures


def read_list_from_files(paths: Iterable[pathlib.Path]) -> Iterator[str]:
    """Read non-empty, non-comment lines from a text files."""
    already_yielded = set()
    for path in paths:
        for line in iter_non_comment_lines(path):
            if line in already_yielded:
                logger = logging.getLogger(__script_name__)
                logger.warning("Duplicate entry in %s: %s", path, line)
            yield line
            already_yielded.add(line)


def str_sorted_set(s: set[Any]) -> str:
    """Returns a string representation of a set with sorted entries."""
    if not s:
        return "set()"
    items_repr = ", ".join(repr(x) for x in sorted(s))
    return f"{{{items_repr}}}"


def check_duplicate_primary_file_extensions(
    media_types: Iterable[EnhancedMediaType],
) -> int:
    """Check that there are no duplicate primary file extensions."""
    file_extensions = collections.defaultdict(set)
    for media_type in media_types:
        for file_extension in media_type.primary_file_extensions:
            file_extensions[file_extension].add(media_type.template)

    duplicates = {k: v for k, v in file_extensions.items() if len(v) > 1}
    if duplicates:
        logger = logging.getLogger(__script_name__)
        logger.warning(
            "%i duplicate primary file extensions found: %s",
            len(duplicates),
            duplicates,
        )
        return 1
    return 0


def check_duplicates(duplicates: set[str], known_duplicates: set[str]) -> int:
    """Check that all duplicate file extensions are acknowledged."""
    logger = logging.getLogger(__script_name__)
    failures = 0

    unknown = duplicates - known_duplicates
    if unknown:
        logger.warning(
            "%i duplicate file extension(s) not mentioned in known duplicates: %s",
            len(unknown),
            str_sorted_set(unknown),
        )
        failures += 1

    unused = known_duplicates - duplicates
    if unused:
        logger.warning(
            "%i unused known duplicate file extension(s): %s",
            len(unused),
            str_sorted_set(unused),
        )
        failures += 1

    return failures


def add_file_extensions(
    media_types: MediaTypeList[MediaType],
    extra_file_extensions: Mapping[str, list[str]],
) -> int:
    """Append file extensions to media types and check consistency."""
    duplicates, unused = media_types.add_file_extensions(extra_file_extensions)

    failures = 0
    if duplicates:
        logger = logging.getLogger(__script_name__)
        for media_type, duplicate in duplicates.items():
            logger.warning(
                "%i duplicate additional file extension(s) for %s: %s",
                len(duplicate),
                media_type,
                duplicate,
            )
            failures += 1
    if unused:
        logger = logging.getLogger(__script_name__)
        logger.warning("%i unused extra file extension(s): %s", len(unused), unused)
        failures += 1
    return failures


def check_unused_lowercase(
    lowercase: list[str], media_types: MediaTypeList[MediaType]
) -> int:
    """Check that all lowercase file extensions are used."""
    failures = 0

    unused = set(lowercase) - media_types.get_all_file_extensions()
    if unused:
        logger = logging.getLogger(__script_name__)
        logger.warning(
            "%i unused lowercase file extension(s): %s",
            len(unused),
            str_sorted_set(unused),
        )
        failures += 1

    return failures


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input",
        action="append",
        type=pathlib.Path,
        help=f"Input IANA CSV file including file extensions column."
        f" Can be specified multiple times. (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=pathlib.Path("media-types.csv"),
        type=pathlib.Path,
        help="Output CSV file (default: %(default)s)",
    )
    parser.add_argument(
        "--known-duplicates",
        action="append",
        type=pathlib.Path,
        help=f"File containing a list of known duplicate file extensions."
        f" Can be specified multiple times. (default: {DEFAULT_KNOWN_DUPLICATES})",
    )
    parser.add_argument(
        "--lowercase",
        type=pathlib.Path,
        default=pathlib.Path("enhancement/lowercase.txt"),
        help="File containing a list of file extensions"
        " that should be converted to lowercase. (default: %(default)s)",
    )
    parser.add_argument(
        "--primary-file-extensions",
        action="append",
        type=pathlib.Path,
        help=f"CSV file listing file extensions and their corresponding media type."
        f" Can be specified multiple times."
        f" (default: {DEFAULT_PRIMARY_FILE_EXTENSIONS})",
    )
    parser.add_argument(
        "--extra-file-extensions",
        action="append",
        default=[],
        type=pathlib.Path,
        help="CSV file listing media types and additional file extensions for them."
        " Can be specified multiple times.",
    )

    args = parser.parse_args()
    if args.input is None:
        args.input = [DEFAULT_INPUT]
    if args.known_duplicates is None:
        args.known_duplicates = [DEFAULT_KNOWN_DUPLICATES]
    if args.primary_file_extensions is None:
        args.primary_file_extensions = [DEFAULT_PRIMARY_FILE_EXTENSIONS]
    return args


def main() -> int:
    """Enhance IANA CSV with primary file extensions."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    media_types: MediaTypeList[MediaType] = MediaTypeList.from_files(args.input)
    extra_file_extensions, total_failures = read_extra_file_extensions_mapping(
        args.extra_file_extensions
    )
    total_failures += add_file_extensions(media_types, extra_file_extensions)

    lowercase = list(read_list_from_files([args.lowercase]))
    total_failures += check_unused_lowercase(lowercase, media_types)

    duplicates = media_types.get_duplicate_file_extensions(lowercase)
    known_duplicates = set(read_list_from_files(args.known_duplicates))
    total_failures += check_duplicates(duplicates, known_duplicates)

    primary_file_extensions, failures = read_mapping_from_csv(
        args.primary_file_extensions, "File Extension", "Media Type"
    )
    total_failures += failures
    enhanced_media_types, failures = enhance_media_types(
        media_types, duplicates, lowercase, primary_file_extensions
    )
    total_failures += failures
    total_failures += check_duplicate_primary_file_extensions(enhanced_media_types)
    enhanced_media_types.sort()
    enhanced_media_types.write_to_csv(args.output)
    return total_failures


if __name__ == "__main__":
    sys.exit(main())
