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
from collections.abc import Callable, Container, Iterable, Iterator, Mapping
from typing import Self, TypeVar

ALLOWED_MISSING_TEMPLATES = {"image/x-emf", "image/x-wmf"}
TOP_LEVEL_TYPES_CSV = "top-level-media-type-names.csv"
SKIP_TOP_LEVEL_TYPES = ("example",)


class ParserFailure(RuntimeError):
    """Base exception raised for errors during file extensions parsing."""


def iter_csv_rows(path: pathlib.Path) -> Iterator[dict[str, str]]:
    """Yields rows from a CSV file."""
    with open(path, encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        yield from reader


def iter_non_comment_lines(path: pathlib.Path) -> Iterator[str]:
    """Yields non-empty, non-comment lines from a file line-by-line."""
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            yield line


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

    def __lt__(self, other: Self) -> bool:
        return self.template.lower() < other.template.lower()

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

    def get_lowercased_file_extensions(self, lowercase: Container[str]) -> list[str]:
        """Returns deduplicated file extensions, lowercasing specified matches."""
        file_extensions = []
        for extension in self.file_extensions:
            if extension in lowercase:
                extension = extension.lower()
            if extension not in file_extensions:
                file_extensions.append(extension)
        return file_extensions


T = TypeVar("T", bound=MediaType)


class MediaTypeList(list[T]):
    """A typed list container for MediaType (or subtype) instances."""

    item_cls: type[T] = MediaType  # type: ignore[assignment]

    @classmethod
    def from_files(cls, files: Iterable[pathlib.Path]) -> Self:
        """Creates an instance populated from the given CSV files."""
        result: Self = cls()
        for path in files:
            for row in iter_csv_rows(path):
                result.append(cls.item_cls.from_csv_dict(row))
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

    def add_file_extensions(
        self, file_extensions: Mapping[str, list[str]]
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Append file extensions to media types.

        Return tuple of duplicates that were skipped and unmatched entries."""
        used = set()
        duplicates: dict[str, list[str]] = {}
        for media_type in self:
            if media_type.template in file_extensions:
                for extension in file_extensions[media_type.template]:
                    if extension in media_type.file_extensions:
                        if media_type.template not in duplicates:
                            duplicates[media_type.template] = []
                        duplicates[media_type.template].append(extension)
                    else:
                        media_type.file_extensions.append(extension)
                used.add(media_type.template)
        return duplicates, {k: v for k, v in file_extensions.items() if k not in used}

    def get_all_file_extensions(self) -> set[str]:
        """Returns all file extensions across all media types."""
        file_extensions = set()
        for media_type in self:
            file_extensions.update(media_type.file_extensions)
        return file_extensions

    def get_duplicate_file_extensions(self, lowercase: Container[str]) -> set[str]:
        """Returns file extensions present in multiple media types."""
        duplicates = set()
        used: set[str] = set()
        for media_type in self:
            file_extensions = set(media_type.get_lowercased_file_extensions(lowercase))
            duplicates.update(file_extensions.intersection(used))
            used.update(file_extensions)
        return duplicates

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


@dataclasses.dataclass
class EnhancedMediaType(MediaType):
    """Media type data enhanced with unique file extensions."""

    unique_file_extensions: list[str]

    @classmethod
    def from_csv_dict(cls, items: dict[str, str]) -> Self:
        """Creates an instance from a CSV row dictionary."""
        return cls(
            items["Name"],
            items["Template"],
            parse_space_separated_list(items["File Extensions"]),
            items["Reference"],
            parse_space_separated_list(items["Unique File Extensions"]),
        )

    @classmethod
    def from_media_type(
        cls, base: MediaType, unique_file_extensions: list[str]
    ) -> Self:
        """Constructs an instance from a base MediaType instance."""
        return cls(
            **dataclasses.asdict(base), unique_file_extensions=unique_file_extensions
        )

    @staticmethod
    def get_csv_dict_keys() -> list[str]:
        """Gets the list of CSV header keys used for CSV serialization."""
        dict_keys = MediaType.get_csv_dict_keys()
        dict_keys.insert(2, "Unique File Extensions")
        return dict_keys

    def as_csv_dict(self) -> dict[str, str]:
        """Converts the instance into a CSV row dictionary."""
        data = super().as_csv_dict()
        data["Unique File Extensions"] = " ".join(self.unique_file_extensions)
        return data


class EnhancedMediaTypeList(MediaTypeList[EnhancedMediaType]):
    """A typed list container for EnhancedMediaType instances."""

    item_cls = EnhancedMediaType


def get_top_level_media_type_names(directory: pathlib.Path) -> Iterator[str]:
    """Yield top-level media type names from the local CSV file."""
    for row in iter_csv_rows(directory / TOP_LEVEL_TYPES_CSV):
        name = row["Name"]
        if name in SKIP_TOP_LEVEL_TYPES:
            continue
        yield name
