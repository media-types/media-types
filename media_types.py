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
import dataclasses
import logging
import os
import pathlib
from collections.abc import Callable, Iterable, Iterator
from typing import Self

ALLOWED_MISSING_TEMPLATES = {"image/x-emf", "image/x-wmf"}
TOP_LEVEL_TYPES_CSV = "top-level-media-type-names.csv"
SKIP_TOP_LEVEL_TYPES = ("example",)


class ParserFailure(RuntimeError):
    """Base exception raised for errors during file extensions parsing."""


def parse_space_separated_list(string: str) -> list[str]:
    """Splits a space-separated string into a list of strings."""
    if not string:
        return []
    return string.split(" ")


@dataclasses.dataclass
class MediaType:
    """Media type data (including file extensions).

    This class represents the media type data provided by IANA.
    """

    name: str
    template: str
    file_extensions: list[str]
    reference: str

    @classmethod
    def from_csv_dict(cls, items: dict[str, str]) -> Self:
        """Creates an instance from a CSV row dictionary."""
        return cls(
            items["Name"],
            items["Template"],
            parse_space_separated_list(items["File Extensions"]),
            items["Reference"],
        )

    @staticmethod
    def get_csv_dict_keys() -> list[str]:
        """Gets the list of CSV header keys used for CSV serialization."""
        return ["Name", "Template", "File Extensions", "Reference"]

    def as_csv_dict(self) -> dict[str, str]:
        """Converts the instance into a CSV row dictionary."""
        return {
            "Name": self.name,
            "Template": self.template,
            "File Extensions": " ".join(self.file_extensions),
            "Reference": self.reference,
        }

    def add_additional_information(
        self,
        file_extension_parser: Callable[[str, str], list[str]],
        directory: pathlib.Path,
    ) -> int:
        """Populates file extensions by reading and parsing the entry's template file.

        Returns number of failures.
        """
        path = directory / self.template
        try:
            content = path.read_text("utf-8")
        except FileNotFoundError as error:
            if self.template in ALLOWED_MISSING_TEMPLATES:
                return 0
            logger = logging.getLogger(__name__)
            logger.error("%s not found", error.filename)
            return 1

        failures = 0
        try:
            self.file_extensions = file_extension_parser(self.template, content)
        except ParserFailure as error:
            logger = logging.getLogger(__name__)
            logger.error("%s", error)
            failures += 1
        return 0


class MediaTypeList(list[MediaType]):
    """A typed list container for MediaType instances."""

    @classmethod
    def from_files(cls, files: Iterable[pathlib.Path]) -> Self:
        """Creates an instance populated from the given CSV files."""
        result: Self = cls()
        for path in files:
            with open(path, encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    result.append(MediaType.from_csv_dict(row))
        return result

    def add_additional_information(
        self,
        file_extension_parser: Callable[[str, str], list[str]],
        directory: pathlib.Path,
    ) -> int:
        """Populates file extensions by reading and parsing the entry's template file.

        Returns number of failures.
        """
        failures = 0
        for media_type in self:
            failures += media_type.add_additional_information(
                file_extension_parser, directory
            )
        return failures

    def write_to_csv(self, path: pathlib.Path) -> None:
        """Writes a list of MediaType instances to a CSV file."""
        fieldnames = self[0].get_csv_dict_keys()
        with open(path, "w", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file, fieldnames=fieldnames, lineterminator=os.linesep
            )
            writer.writeheader()
            for item in self:
                writer.writerow(item.as_csv_dict())


def get_top_level_media_type_names(directory: pathlib.Path) -> Iterator[str]:
    """Yield top-level media type names from the local CSV file."""
    with open(directory / TOP_LEVEL_TYPES_CSV, encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            name = row["Name"]
            if name in SKIP_TOP_LEVEL_TYPES:
                continue
            yield name
