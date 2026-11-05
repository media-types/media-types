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

# pylint: disable=too-many-lines

"""Generate IANA CSV file with additional file extensions column."""

import argparse
import dataclasses
import email.utils
import hashlib
import logging
import os
import pathlib
import re
import sys
import unittest
from collections.abc import Iterator, Sequence
from typing import Self

from media_types import (
    IntendedUsageType,
    MediaType,
    MediaTypeList,
    ParserFailure,
    get_top_level_media_type_names,
    iter_csv_rows,
    iter_non_comment_lines,
    parse_space_separated_list,
    typecast_intended_usage,
)

DEFAULT_DIRECTORY = pathlib.Path("iana")
DEFAULT_DATES_MANUAL = pathlib.Path("parser/dates/manual.csv")
DEFAULT_DATES_MISSING_LAST_UPDATED = pathlib.Path(
    "parser/dates/missing_last_updated.csv"
)
DEFAULT_DATES_MISSING_REGISTERED = pathlib.Path("parser/dates/missing_registered.csv")
DEFAULT_DATES_RFCS = pathlib.Path("parser/dates/rfcs.csv")
DEFAULT_FILE_EXTENSIONS_MANUAL = pathlib.Path("parser/file_extensions/manual.csv")
DEFAULT_FILE_EXTENSIONS_MAPPING = pathlib.Path("parser/file_extensions/mapping.tsv")
DEFAULT_FILE_EXTENSIONS_MISSING = pathlib.Path("parser/file_extensions/missing.csv")
DEFAULT_INTENDED_USAGE_MANUAL = pathlib.Path("parser/intended_usage/manual.csv")
DEFAULT_INTENDED_USAGE_MISSING = pathlib.Path("parser/intended_usage/missing.csv")
LOG_FORMAT = "%(name)s %(levelname)s: %(message)s"
FILE_EXTENSIONS_RE = re.compile(
    r"[Ff]ile\s[Ee]xtensions? ?(?:\(s\))?(?:\s*)[:\n](.*?)(?:\n> ?)*"
    r"(?:(?:[34]\. |[-*o]  ?)?Macintosh\s[Ff]ile\s[Tt]ype\s[Cc]odes? ?(?:\(s\))?"
    r"|(?:4\.\s|Apple\s|macOS\s)Uniform\sType\sIdentifier(?:\(s\))?"
    r"|Base URI|Fragment identifiers|Intended [Uu]sage"
    r"|Required parameters|Windows Clipboard Name"
    r"|Person(?:al)? (?:(?:and|&) e-?mail address )?"
    r"(?:to contact )?for further +information) ?[:\n]",
    re.DOTALL,
)
INTENDED_USAGE_RE = re.compile(
    r"Intended [Uu]sage\s*?[:\n]\s*?"
    r"(COMMON|LIMITED USE|OBSOLETE|[Cc]ommon|[Ll]imited [Uu]se|Obsolete)"
)
NO_ADDITIONAL_INFORMATION_RE = re.compile(
    r"Additional\s[Ii]nformation:\s*(|[Nn][Oo][Nn][Ee]|[Nn]/[Aa]|\(none\))\.?\s*"
    r"(?:o )?(?:Intended [Uu]sage|Contact(?: for further information)?"
    r"|Person(?:al)? (?:(?:and|&) e-?mail address )?"
    r"(?:to contact )?for further +information) ?[:\n]",
    re.DOTALL,
)
NOT_SPECIFIED_RE = re.compile(
    r"^(-|any|n/a|undefined|unknown|not (applicable|available|designed yet)"
    r"|do not apply|\(none\)|-none-|<none defined>|none ?(disclosed|yet)?)[.,]?$"
)
SPLIT_RE = re.compile(r"\s*(?:,? and |,? or |[,;\s])\s*")
__script_name__ = os.path.basename(sys.argv[0]) if __name__ == "__main__" else __name__

# Date parsing regular expressions
MONTH_MAP = {
    "January": "01",
    "February": "02",
    "March": "03",
    "April": "04",
    "May": "05",
    "June": "06",
    "July": "07",
    "August": "08",
    "September": "09",
    "October": "10",
    "November": "11",
    "December": "12",
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
}
EMAIL_DATE_RE = re.compile(
    r"^(?:Date|Sent):\s*((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun).*)$", re.MULTILINE
)
EMAIL_FROM_DATE_RE = re.compile(
    r"^From [A-Za-z._]+&[A-Za-z._]+\s*((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun).*)$",
    re.MULTILINE,
)
ISO8601_DATE_RE = re.compile("^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
OLD_DATE_RE = re.compile(
    "^(?:([0-3]?[0-9])[- ])?(" + "|".join(MONTH_MAP) + r")[- ]([0-9]{4})$"
)
OLD_DATE_INVERSE_RE = re.compile(
    "^([0-9]{4}) (" + "|".join(MONTH_MAP) + r") ([0-3]?[0-9])$"
)
REGISTERED_LAST_UPDATED_RE = re.compile(
    r"\((?:[Rr]egistered|[Ff]ile created|created)(?: in)? ([0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?)"
    r"(?: (?:per|through|via) RFC ?[0-9]+)?[,;]"
    r"(?: last| updated [0-9]{4}-[0-9]{2}-[0-9]{2},)? updated ([0-9]{4}-[0-9]{2}-[0-9]{2})"
    r"(?:; (?:see RFC[0-9]+|obsoleted by[A-Za-z0-9/+ \n]+))?\)"
)
REGISTERED_RFC_LAST_UPDATED_RE = re.compile(
    r"\((?:originally )?registered by \[?RFC ?([0-9]+)\]?"
    r"[,;] last updated ([0-9]{4}-[0-9]{2}-[0-9]{2})\)"
)
REGISTERED_RFC_UPDATED_RFC_RE = re.compile(
    r"\((?:registered|defined) (?:by|in) RFC ?([0-9]+)[,;]"
    r"(?: optional parameters)? (?:added|updated|deprecated) (?:by|in) RFC ?([0-9]+)"
    r"(?:, published October [0-9]{4})?\)"
)
RFC_REGISTERED_UPDATED_RE = re.compile(
    r"\((?:published in )?RFC ?([0-9]+) (?:published|in) ((?:"
    + "|".join(MONTH_MAP)
    + r") [0-9]{4}), (?:subtype last |last )?updated"
    + r" ([0-9]{4}-[0-9]{2}-[0-9]{2}|(?:[0-3]?[0-9] )?(?:"
    + "|".join(MONTH_MAP)
    + r") [0-9]{4})(?:\s+(?:per|via) RFC ?([0-9]+))?"
    r"(?:\.\s+RFC [0-9]+ does not contain a registration template\.)?\)"
)
RFC_REGISTERED_RE = re.compile(
    r"\(RFC ?([0-9]+) published ((?:" + "|".join(MONTH_MAP) + r") [0-9]{4})\)"
)
REGISTERED_RFC_RE = re.compile(
    r"\((?:registered (?:by|in|via)|per) (?:RFC)? ?([0-9]+)\)"
)
REGISTERED_RE = re.compile(
    r"[([](?:[Rr]egistered|[Ff]iled? [Cc]reated|[Cc]reated|submitted to IANA)"
    r" ([0-9]{4}-[0-9]{2}(?:-[0-9]{2})?)(?: per RFC ?[0-9]+)?[)\]]"
)
REGISTERED_OLD_RE = re.compile(
    r"[([](?:[Rr]egistered|[Ff]iled? [Cc]reated|[Cc]reated) (?:on )?"
    r" ?((?:[0-3]?[0-9]{1,3}[- ])?(?:"
    + "|".join(MONTH_MAP)
    + r")[- ][0-3]?[0-9]{1,3})\.?[)\]]"
)
LAST_UPDATED_RE = re.compile(
    r"\((?:(?:[Ll]ast|[Ff]ile) (?:[Uu]pdated?|modified)|deprecated)"
    r" ([0-9]{4}-[0-9]{2}-[0-9]{2})(?:; (?:obsoleted|OBSOLETE))?\)"
)
LAST_UPDATED_OLD_RE = re.compile(
    r"\((?:[Ll]ast|[Ff]ile|References) [Uu]pdated"
    r" ((?:[0-3]?[0-9]{1,3} )?(?:" + "|".join(MONTH_MAP) + r") [0-3]?[0-9]{1,3})\.?\)"
)


class ChecksumMismatch(ParserFailure):
    """Raised when checksum does not match checksum given in manual/missing CSV."""

    def __init__(self, template: str, expected: str, got: str) -> None:
        self.template = template
        self.expected = expected
        self.got = got

    def __str__(self) -> str:
        return (
            f"BLAKE2b 128-bit checksum mismatch for '{self.template}':"
            f" expected {self.expected}, but got {self.got}"
        )


class MissingRFCDate(ParserFailure):
    """Raised when no publish date for a RFC was provided."""


class NoDatesFound(ParserFailure):
    """Raised when no dates were found."""


class NoFileExtensionsFound(ParserFailure):
    """Raised when no file extensions were found."""


class NoIntendedUsageFound(ParserFailure):
    """Raised when no intended usage was found."""


@dataclasses.dataclass
class ManualDates:
    """Row of dates manual CSV file."""

    checksum: str
    media_type: str
    registered: str
    last_updated: str

    @classmethod
    def from_csv_dict(cls, items: dict[str, str]) -> Self:
        """Creates an instance from a CSV row dictionary."""
        return cls(
            items["BLAKE2b Checksum"],
            items["Media Type"],
            items["Registered"],
            items["Last Updated"],
        )


@dataclasses.dataclass
class ManualFileExtensions:
    """Row of file-extensions manual CSV file."""

    checksum: str
    media_type: str
    file_extensions: list[str]

    @classmethod
    def from_csv_dict(cls, items: dict[str, str]) -> Self:
        """Creates an instance from a CSV row dictionary."""
        return cls(
            items["BLAKE2b Checksum"],
            items["Media Type"],
            parse_space_separated_list(items["File Extensions"] or ""),
        )


@dataclasses.dataclass
class ManualIntendedUsage:
    """Row of intended usage manual CSV file."""

    checksum: str
    media_type: str
    intended_usage: IntendedUsageType

    @classmethod
    def from_csv_dict(cls, items: dict[str, str]) -> Self:
        """Creates an instance from a CSV row dictionary."""
        return cls(
            items["BLAKE2b Checksum"],
            items["Media Type"],
            typecast_intended_usage(items["Intended Usage"] or ""),
        )


def blake2b_128bit(text: str) -> str:
    """Calculates the 128-bit (32-hex-character) BLAKE2b hash of a string."""
    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()


def load_file_extensions_manual(path: pathlib.Path) -> dict[str, ManualFileExtensions]:
    """Load file extensions manual CSV file."""
    mapping = {}
    for row in iter_csv_rows(path):
        value = ManualFileExtensions.from_csv_dict(row)
        mapping[value.media_type] = value
    return mapping


def load_dates_manual_csv(path: pathlib.Path) -> dict[str, ManualDates]:
    """Load dates manual CSV file."""
    mapping = {}
    for row in iter_csv_rows(path):
        value = ManualDates.from_csv_dict(row)
        mapping[value.media_type] = value
    return mapping


def load_dates_rfcs_csv(path: pathlib.Path) -> dict[int, str]:
    """Load dates rfcs CSV file."""
    mapping = {}
    for row in iter_csv_rows(path):
        mapping[int(row["RFC"])] = row["Date published"]
    return mapping


def load_file_extensions_mapping(path: pathlib.Path) -> dict[str, list[str]]:
    """Load file extensions mapping tab-separated value file."""
    mapping = {}
    for line in iter_non_comment_lines(path):
        extensions_str, key = line.split("\t")
        mapping[key] = parse_space_separated_list(extensions_str)
    return mapping


def load_intended_usage_manual_csv(
    path: pathlib.Path,
) -> dict[str, ManualIntendedUsage]:
    """Load intended usage manual CSV file."""
    mapping = {}
    for row in iter_csv_rows(path):
        value = ManualIntendedUsage.from_csv_dict(row)
        mapping[value.media_type] = value
    return mapping


def load_missing_csv(path: pathlib.Path) -> dict[str, str]:
    """Load CSV file that lists media types and their BLAKE2b checksums."""
    mapping = {}
    for row in iter_csv_rows(path):
        mapping[row["Media Type"]] = row["BLAKE2b Checksum"]
    return mapping


def verify_checksum(template: str, content: str, expected_checksum: str) -> None:
    """Validate the content against the given expected checksum."""
    checksum = blake2b_128bit(content)
    if checksum != expected_checksum:
        raise ChecksumMismatch(template, expected_checksum, checksum)


def _strip(text: str) -> str:
    if text.startswith("'") and text.endswith("'"):
        text = text[1:-1]
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    return text.removeprefix(".").removeprefix("*.")


def _parse_date(date_str: str) -> str:
    if ISO8601_DATE_RE.match(date_str):
        return date_str

    match = OLD_DATE_INVERSE_RE.match(date_str)
    if match:
        year, month, day = match.groups()
        return f"{year}-{MONTH_MAP[month]}-{int(day):02d}"

    match = OLD_DATE_RE.match(date_str)
    assert match
    day, month, year = match.groups()
    if not day:
        return f"{year}-{MONTH_MAP[month]}"
    return f"{year}-{MONTH_MAP[month]}-{int(day):02d}"


def _parse_email_date(date_str: str) -> str:
    return email.utils.parsedate_to_datetime(date_str).date().isoformat()


@dataclasses.dataclass
# pylint: disable-next=too-many-instance-attributes
class DateParser:
    """Parser for registration and last updated dates."""

    manual: dict[str, ManualDates]
    missing_last_updated: dict[str, str]
    missing_registered: dict[str, str]
    rfcs: dict[int, str]

    used_manual: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )
    used_missing_last_updated: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )
    used_missing_registered: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )
    used_rfcs: set[int] = dataclasses.field(default_factory=set, init=False, repr=False)

    @classmethod
    def from_files(
        cls,
        manual_file: pathlib.Path,
        missing_last_updated_file: pathlib.Path,
        missing_registered_file: pathlib.Path,
        rfcs_file: pathlib.Path,
    ) -> Self:
        """Construct an instance by loading rules from file paths."""
        manual = load_dates_manual_csv(manual_file)
        missing_last_updated = load_missing_csv(missing_last_updated_file)
        missing_registered = load_missing_csv(missing_registered_file)
        rfcs = load_dates_rfcs_csv(rfcs_file)
        return cls(manual, missing_last_updated, missing_registered, rfcs)

    def _check_missing_dates(
        self, template: str, content: str, registered: str, last_updated: str
    ) -> None:
        missing = []
        if not registered:
            if template not in self.missing_registered:
                missing.append("registration")
            else:
                verify_checksum(template, content, self.missing_registered[template])
                self.used_missing_registered.add(template)

        if not last_updated:
            if template not in self.missing_last_updated:
                missing.append("last updated")
            else:
                verify_checksum(template, content, self.missing_last_updated[template])
                self.used_missing_last_updated.add(template)

        if missing:
            raise NoDatesFound(
                f"Found no {' and '.join(missing)} date for '{template}'."
            )

    def _check_rfc_date(self, rfc: int, date: str) -> str:
        if len(date) >= 10:
            return date
        rfc_date = self.get_rfc_date(rfc)
        assert rfc_date.startswith(date), f"{rfc_date} does not start with {date}"
        return rfc_date

    def _parse_combined(self, template: str, content: str) -> tuple[str, str]:
        found = REGISTERED_LAST_UPDATED_RE.findall(content)
        if found:
            assert len(found) == 1, f"multiple dates for {template}: {found}"
            registered, last_updated = found[0]
            return (registered, last_updated)

        found = REGISTERED_RFC_LAST_UPDATED_RE.findall(content)
        if found:
            assert len(found) == 1, f"multiple dates for {template}: {found}"
            rfc_registred, last_updated = found[0]
            registered = self.get_rfc_date(int(rfc_registred))
            return (registered, last_updated)

        found = REGISTERED_RFC_UPDATED_RFC_RE.findall(content)
        if found:
            assert len(found) == 1, f"multiple dates for {template}: {found}"
            rfc_registred, rfc_updated = found[0]
            registered = self.get_rfc_date(int(rfc_registred))
            last_updated = self.get_rfc_date(int(rfc_updated))
            return (registered, last_updated)

        found = RFC_REGISTERED_UPDATED_RE.findall(content)
        if found:
            assert len(found) == 1, f"multiple dates for {template}: {found}"
            rfc_registered, registered_str, last_updated_str, rfc_updated = found[0]
            registered = _parse_date(registered_str)
            last_updated = _parse_date(last_updated_str)
            registered = self._check_rfc_date(int(rfc_registered), registered)
            if rfc_updated:
                last_updated = self._check_rfc_date(int(rfc_updated), last_updated)
            elif registered_str == last_updated_str:
                last_updated = registered
            return (registered, last_updated)

        return ("", "")

    def _parse_registered(self, template: str, content: str) -> str:
        found = REGISTERED_RE.findall(content)
        if found:
            assert (
                len(set(found)) == 1
            ), f"multiple registration dates for {template}: {found}"
            assert isinstance(found[0], str)
            return found[0]

        found = REGISTERED_OLD_RE.findall(content)
        if found:
            assert (
                len(set(found)) == 1
            ), f"multiple registration dates for {template}: {found}"
            return _parse_date(found[0])

        found = RFC_REGISTERED_RE.findall(content)
        if found:
            assert (
                len(set(found)) == 1
            ), f"multiple registration dates for {template}: {found}"
            rfc_registered, registered = found[0]
            return self._check_rfc_date(int(rfc_registered), _parse_date(registered))

        found = REGISTERED_RFC_RE.findall(content)
        if found:
            assert (
                len(set(found)) == 1
            ), f"multiple registration dates for {template}: {found}"
            return self.get_rfc_date(int(found[0]))

        for pattern in (EMAIL_DATE_RE, EMAIL_FROM_DATE_RE):
            found = pattern.findall(content)
            if found:
                assert (
                    len(set(found)) == 1
                ), f"multiple registration dates for {template}: {found}"
                return _parse_email_date(found[0])

        return ""

    def _parse_last_updated(self, template: str, content: str) -> str:
        found = LAST_UPDATED_RE.findall(content)
        if found:
            assert (
                len(set(found)) == 1
            ), f"multiple last updated dates for {template}: {found}"
            assert isinstance(found[0], str)
            return found[0]

        found = LAST_UPDATED_OLD_RE.findall(content)
        if found:
            assert (
                len(set(found)) == 1
            ), f"multiple last updated dates for {template}: {found}"
            return _parse_date(found[0])

        return ""

    def get_rfc_date(self, rfc: int) -> str:
        """Get the RFC publish date and mark it as used."""
        if rfc not in self.rfcs:
            raise MissingRFCDate(f"Missing publish date for RFC {rfc}.")
        self.used_rfcs.add(rfc)
        return self.rfcs[rfc]

    def parse(self, template: str, content: str) -> tuple[str, str]:
        """Extract intended usage from template text content."""
        if content.strip() == "No registration template available.":
            return ("", "")

        if template in self.manual:
            verify_checksum(template, content, self.manual[template].checksum)
            self.used_manual.add(template)
            dates = self.manual[template]
            self._check_missing_dates(
                template, content, dates.registered, dates.last_updated
            )
            return (dates.registered, dates.last_updated)

        registered, last_updated = self._parse_combined(template, content)
        if registered and last_updated:
            return (registered, last_updated)

        registered = self._parse_registered(template, content)
        last_updated = self._parse_last_updated(template, content)
        if registered and last_updated:
            return (registered, last_updated)

        self._check_missing_dates(template, content, registered, last_updated)
        return (registered, last_updated)

    def check_unused(self) -> int:
        """Check configs that were never matched or used."""
        logger = logging.getLogger(__script_name__)
        unused_count = 0
        for name, data, used in (
            ("manual", self.manual, self.used_manual),
            (
                "missing last updated",
                self.missing_last_updated,
                self.used_missing_last_updated,
            ),
            (
                "missing registered",
                self.missing_registered,
                self.used_missing_registered,
            ),
            ("rfcs", self.rfcs, self.used_rfcs),
        ):
            unused = [key for key in data if key not in used]
            if unused:
                logger.warning(
                    "%i unused entrie(s) in dates %s file: %s",
                    len(unused),
                    name,
                    unused,
                )
                unused_count += len(unused)
        return unused_count


@dataclasses.dataclass
class FileExtensionsParser:
    """Parser for file extensions."""

    manual: dict[str, ManualFileExtensions]
    mapping: dict[str, list[str]]
    missing: dict[str, str]

    used_manual: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )
    used_mapping: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )
    used_missing: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )

    @classmethod
    def from_files(
        cls,
        manual_file: pathlib.Path,
        mapping_file: pathlib.Path,
        missing_file: pathlib.Path,
    ) -> Self:
        """Construct an instance by loading rules from file paths."""
        manual = load_file_extensions_manual(manual_file)
        mapping = load_file_extensions_mapping(mapping_file)
        missing = load_missing_csv(missing_file)
        return cls(manual, mapping, missing)

    # pylint: disable-next=too-many-return-statements
    def parse(self, template: str, content: str) -> list[str]:
        """Extract file extensions from template text content."""
        if content.strip() == "No registration template available.":
            return []

        if template in self.manual:
            verify_checksum(template, content, self.manual[template].checksum)
            self.used_manual.add(template)
            return self.manual[template].file_extensions

        clean_content = re.sub(
            r"Change History\n--------------.*", "", content, flags=re.DOTALL
        )
        found = FILE_EXTENSIONS_RE.findall(clean_content)
        if not found:
            if NO_ADDITIONAL_INFORMATION_RE.search(clean_content):
                return []
            if template in self.missing:
                verify_checksum(template, content, self.missing[template])
                self.used_missing.add(template)
                return []
            raise NoFileExtensionsFound(f"Found no file extensions for '{template}'.")

        found = [x.strip() for x in found]
        if len(found) == 2 and found[1] == "none":
            del found[1]
        if len(set(found)) > 1:
            raise ParserFailure(
                f"Found multiple file extensions for '{template}': {found!r}"
            )

        unwrapped = re.sub(r"[\t ]*\n[\t ]*", " ", found[0], flags=re.DOTALL)
        if NOT_SPECIFIED_RE.match(unwrapped.lower()):
            return []
        if unwrapped in self.mapping:
            self.used_mapping.add(unwrapped)
            return self.mapping[unwrapped]
        extensions = [_strip(x) for x in SPLIT_RE.split(unwrapped.strip(",;"))]
        return extensions

    def check_unused(self) -> int:
        """Check configs that were never matched or used."""
        logger = logging.getLogger(__script_name__)
        unused_count = 0
        for name, data, used in (
            ("manual", self.manual, self.used_manual),
            ("mapping", self.mapping, self.used_mapping),
            ("missing", self.missing, self.used_missing),
        ):
            unused = [key for key in data if key not in used]
            if unused:
                logger.warning(
                    "%i unused entrie(s) in file extensions %s file: %s",
                    len(unused),
                    name,
                    unused,
                )
                unused_count += len(unused)
        return unused_count


@dataclasses.dataclass
class IntendedUsageParser:
    """Parser for intended usage."""

    manual: dict[str, ManualIntendedUsage]
    missing: dict[str, str]

    used_manual: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )
    used_missing: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )

    @classmethod
    def from_files(cls, manual_file: pathlib.Path, missing_file: pathlib.Path) -> Self:
        """Construct an instance by loading rules from file paths."""
        manual = load_intended_usage_manual_csv(manual_file)
        missing = load_missing_csv(missing_file)
        return cls(manual, missing)

    def parse(self, template: str, content: str) -> IntendedUsageType:
        """Extract intended usage from template text content."""
        if content.strip() == "No registration template available.":
            return ""

        if template in self.manual:
            verify_checksum(template, content, self.manual[template].checksum)
            self.used_manual.add(template)
            return self.manual[template].intended_usage

        found = INTENDED_USAGE_RE.findall(content)
        if not found:
            if template in self.missing:
                verify_checksum(template, content, self.missing[template])
                self.used_missing.add(template)
                return ""
            raise NoIntendedUsageFound(f"Found no intended usage for '{template}'.")
        assert len(set(found)) == 1
        return typecast_intended_usage(found[0].capitalize())

    def check_unused(self) -> int:
        """Check configs that were never matched or used."""
        logger = logging.getLogger(__script_name__)
        unused_count = 0
        for name, data, used in (
            ("manual", self.manual, self.used_manual),
            ("missing", self.missing, self.used_missing),
        ):
            unused = [key for key in data if key not in used]
            if unused:
                logger.warning(
                    "%i unused entrie(s) in intended usage %s file: %s",
                    len(unused),
                    name,
                    unused,
                )
                unused_count += len(unused)
        return unused_count


def iter_media_types(directory: pathlib.Path) -> Iterator[MediaType]:
    """Iterate over media types loaded from CSV files in a directory."""
    for top_level_media_type in get_top_level_media_type_names(directory):
        path = directory / f"{top_level_media_type}.csv"
        for row in iter_csv_rows(path):
            yield MediaType.from_upstream_iana_csv_dict(row)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser()
    # pylint: disable-next=duplicate-code
    parser.add_argument(
        "-d",
        "--directory",
        default=DEFAULT_DIRECTORY,
        type=pathlib.Path,
        help="directory containing the input IANA media type files"
        " (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=pathlib.Path("iana.csv"),
        type=pathlib.Path,
        help="Output CSV file (default: %(default)s)",
    )
    parser.add_argument(
        "--dates-manual",
        default=DEFAULT_DATES_MANUAL,
        type=pathlib.Path,
        help="Path to the CSV file containing mapping of media types"
        " to registered and last updated dates. (default: %(default)s)",
    )
    parser.add_argument(
        "--dates-missing-last-updated",
        default=DEFAULT_DATES_MISSING_LAST_UPDATED,
        type=pathlib.Path,
        help="Path to the CSV file listing media types that do not specify"
        " last updated dates (default: %(default)s)",
    )
    parser.add_argument(
        "--dates-missing-registered",
        default=DEFAULT_DATES_MISSING_REGISTERED,
        type=pathlib.Path,
        help="Path to the CSV file listing media types that do not specify"
        " registered dates (default: %(default)s)",
    )
    parser.add_argument(
        "--dates-rfcs",
        default=DEFAULT_DATES_RFCS,
        type=pathlib.Path,
        help="Path to the CSV file listing RFCs and their publish dates"
        " (default: %(default)s)",
    )
    parser.add_argument(
        "--file-extensions-manual",
        default=DEFAULT_FILE_EXTENSIONS_MANUAL,
        type=pathlib.Path,
        help="Path to the CSV file containing mapping of media types"
        " to file extensions. This is the last resort."
        " Use the mapping file instead if possible. (default: %(default)s)",
    )
    parser.add_argument(
        "--file-extensions-mapping",
        default=DEFAULT_FILE_EXTENSIONS_MAPPING,
        type=pathlib.Path,
        help="Path to the TSV file mapping text to file extensions"
        " (default: %(default)s)",
    )
    parser.add_argument(
        "--file-extensions-missing",
        default=DEFAULT_FILE_EXTENSIONS_MISSING,
        type=pathlib.Path,
        help="Path to the CSV file listing media types that do not specify"
        " file extensions (default: %(default)s)",
    )
    parser.add_argument(
        "--intended-usage-manual",
        default=DEFAULT_INTENDED_USAGE_MANUAL,
        type=pathlib.Path,
        help="Path to the CSV file containing mapping of media types"
        " to intended usage. This is the last resort. (default: %(default)s)",
    )
    parser.add_argument(
        "--intended-usage-missing",
        default=DEFAULT_INTENDED_USAGE_MISSING,
        type=pathlib.Path,
        help="Path to the CSV file listing media types that do not specify"
        " intended usage (default: %(default)s)",
    )
    return parser.parse_args(argv[1:])


def main(argv: Sequence[str]) -> int:
    """Generate IANA CSV file with additional file extensions column."""
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)

    date_parser = DateParser.from_files(
        args.dates_manual,
        args.dates_missing_last_updated,
        args.dates_missing_registered,
        args.dates_rfcs,
    )
    file_extensions_parser = FileExtensionsParser.from_files(
        args.file_extensions_manual,
        args.file_extensions_mapping,
        args.file_extensions_missing,
    )
    intended_usage_parser = IntendedUsageParser.from_files(
        args.intended_usage_manual, args.intended_usage_missing
    )
    media_types = MediaTypeList(iter_media_types(args.directory))
    failures = media_types.add_additional_information(
        date_parser.parse,
        file_extensions_parser.parse,
        intended_usage_parser.parse,
        args.directory,
    )
    date_parser.check_unused()
    file_extensions_parser.check_unused()
    intended_usage_parser.check_unused()
    media_types.write_to_csv(args.output)
    return failures


# pylint: disable-next=too-many-public-methods
class TestFileExtensionsParser(unittest.TestCase):
    # pylint: disable=missing-function-docstring
    """Test cases for FileExtensionsParser class."""

    def parse_file(self, template: str) -> list[str] | None:
        path = DEFAULT_DIRECTORY / template
        content = path.read_text("utf-8")
        parser = FileExtensionsParser({}, {}, {})
        return parser.parse(template, content)

    def test_additional_information_followed_by_contact(self) -> None:
        self.assertEqual(self.parse_file("text/encaprtp"), [])

    def test_additional_information_followed_by_intended_usage(self) -> None:
        self.assertEqual(self.parse_file("audio/SMV0"), [])

    def test_additional_information_n_a(self) -> None:
        self.assertEqual(self.parse_file("video/evc"), [])

    def test_additional_information_none(self) -> None:
        self.assertEqual(self.parse_file("video/H263"), [])

    def test_content_with_change_history(self) -> None:
        self.assertEqual(self.parse_file("video/vnd.mpegurl"), ["mxu", "m4u"])

    def test_dash(self) -> None:
        self.assertEqual(self.parse_file("audio/vnd.4SB"), [])

    def test_duplicate_identical_entries(self) -> None:
        self.assertEqual(self.parse_file("application/prs.cyn"), [])

    def test_duplicate_second_is_none(self) -> None:
        self.assertEqual(self.parse_file("application/vnd.ibm.MiniPay"), ["mpy"])

    def test_email_reply(self) -> None:
        self.assertEqual(self.parse_file("application/vnd.ms-fontobject"), ["eot"])

    def test_extensions_double_plural(self) -> None:
        self.assertEqual(self.parse_file("application/tzif"), [])

    def test_file_extension(self) -> None:
        self.assertEqual(self.parse_file("application/yang"), ["yang"])

    def test_file_extension_s(self) -> None:
        self.assertEqual(self.parse_file("application/pkixcmp"), ["PKI"])

    def test_file_extensions(self) -> None:
        self.assertEqual(self.parse_file("audio/AMR"), ["amr", "AMR"])

    def test_file_extensions_capitalized(self) -> None:
        self.assertEqual(self.parse_file("audio/G711-0"), [])

    def test_file_extensions_without_colon(self) -> None:
        self.assertEqual(self.parse_file("application/srgs"), ["gram"])

    def test_followed_by_base_uri(self) -> None:
        self.assertEqual(self.parse_file("text/n3"), ["n3"])

    def test_followed_by_contact_information(self) -> None:
        self.assertEqual(self.parse_file("image/jxr"), ["jxr"])

    def test_followed_by_intended_usage(self) -> None:
        self.assertEqual(self.parse_file("application/dash-patch+xml"), ["mpp"])

    def test_followed_by_required_parameters(self) -> None:
        self.assertEqual(self.parse_file("application/vnd.osa.netdeploy"), ["ndc"])

    def test_followed_by_windows_clipboard_name(self) -> None:
        self.assertEqual(self.parse_file("application/sdf+json"), ["sdf.json"])

    def test_fragment_identifiers(self) -> None:
        self.assertEqual(self.parse_file("application/atom+xml"), ["atom"])

    def test_list_none(self) -> None:
        self.assertEqual(self.parse_file("application/ace+json"), [])

    def test_list_with_dash(self) -> None:
        self.assertEqual(self.parse_file("application/dpop+jwt"), [])

    def test_list_with_o(self) -> None:
        self.assertEqual(self.parse_file("application/cbor-seq"), [])

    def test_list_with_star(self) -> None:
        self.assertEqual(self.parse_file("application/cbor"), ["cbor"])

    def test_multiple_and_separated(self) -> None:
        self.assertEqual(
            self.parse_file("application/vnd.sus-calendar"), ["sus", "susp"]
        )

    def test_multiple_comma_or_separated(self) -> None:
        self.assertEqual(self.parse_file("application/vnd.hp-hpid"), ["hpi", "hpid"])

    def test_multiple_comma_separated(self) -> None:
        self.assertEqual(self.parse_file("image/jpeg"), ["jpg", "jpeg"])

    def test_multiple_or_without_comma(self) -> None:
        self.assertEqual(
            self.parse_file("image/avif"), ["avif", "heif", "heifs", "hif"]
        )

    def test_multiple_semicolon_separated(self) -> None:
        self.assertEqual(self.parse_file("application/vnd.erofs"), ["erofs", "0fs"])

    def test_multiple_file_extensions(self) -> None:
        with self.assertRaises(ParserFailure) as cm:
            self.parse_file("application/vnd.kde.kspread")
        self.assertEqual(
            str(cm.exception),
            "Found multiple file extensions for 'application/vnd.kde.kspread':"
            " ['KSP', 'KWT, KWD']",
        )

    def test_multiple_space_separated(self) -> None:
        self.assertEqual(self.parse_file("text/vcard"), ["vcf", "vcard"])

    def test_n_a_lowercase(self) -> None:
        self.assertEqual(self.parse_file("application/passport"), [])

    def test_n_a_uppercase(self) -> None:
        self.assertEqual(self.parse_file("application/cwt"), [])

    def test_n_a_with_dot(self) -> None:
        self.assertEqual(self.parse_file("audio/tone"), [])

    def test_no_registration_template_available(self) -> None:
        self.assertEqual(self.parse_file("text/plain"), [])

    def test_none_in_brackets(self) -> None:
        self.assertEqual(self.parse_file("application/cfw"), [])

    def test_not_applicable_dot(self) -> None:
        self.assertEqual(self.parse_file("text/example"), [])

    def test_only_additional_information(self) -> None:
        self.assertEqual(self.parse_file("application/IOTP"), [])

    def test_quoted_double(self) -> None:
        self.assertEqual(self.parse_file("text/vtt"), ["vtt"])

    def test_quoted_single(self) -> None:
        self.assertEqual(self.parse_file("audio/ATRAC3"), ["at3", "aa3", "omg"])

    def test_single_with_dot(self) -> None:
        self.assertEqual(self.parse_file("text/css"), ["css"])

    def test_single_with_star_dot(self) -> None:
        self.assertEqual(self.parse_file("application/efi"), ["efi"])

    def test_single_without_dot(self) -> None:
        self.assertEqual(self.parse_file("image/webp"), ["webp"])

    def test_trailing_comma(self) -> None:
        self.assertEqual(self.parse_file("application/clue+xml"), ["xml"])

    def test_undefined(self) -> None:
        self.assertEqual(self.parse_file("video/vnd.directv.mpeg"), [])

    def test_no_file_extensions_found(self) -> None:
        with self.assertRaises(NoFileExtensionsFound):
            self.parse_file("text/rtf")

    def test_checksum_mismatch(self) -> None:
        missing = {"audio/ac3": "cae66941d9efbd404e4d88758ea67670"}
        parser = FileExtensionsParser({}, {}, missing)
        with self.assertRaises(ChecksumMismatch) as cm:
            parser.parse("audio/ac3", "some content")
        self.assertEqual(
            str(cm.exception),
            "BLAKE2b 128-bit checksum mismatch for 'audio/ac3':"
            " expected cae66941d9efbd404e4d88758ea67670,"
            " but got 85b7c6860119555c208d7718663581f2",
        )

    def test_check_unused(self) -> None:
        missing = {"audio/ac3": "cae66941d9efbd404e4d88758ea67670"}
        parser = FileExtensionsParser({}, {}, missing)
        with self.assertLogs(__script_name__, level=logging.WARNING) as context_manager:
            unused_count = parser.check_unused()
        self.assertRegex(context_manager.output[0], "audio/ac3")
        self.assertEqual(len(context_manager.output), 1)
        self.assertEqual(unused_count, 1)

    def test_parse_full(self) -> None:
        parser = FileExtensionsParser.from_files(
            DEFAULT_FILE_EXTENSIONS_MANUAL,
            DEFAULT_FILE_EXTENSIONS_MAPPING,
            DEFAULT_FILE_EXTENSIONS_MISSING,
        )
        media_types = MediaTypeList(iter_media_types(DEFAULT_DIRECTORY))
        self.assertEqual(
            media_types.add_additional_information(
                lambda _a, _b: ("", ""),
                parser.parse,
                lambda _a, _b: "",
                DEFAULT_DIRECTORY,
            ),
            0,
        )
        self.assertEqual(parser.check_unused(), 0)


class TestIntendedUsageParser(unittest.TestCase):
    # pylint: disable=missing-function-docstring
    """Test cases for IntendedUsageParser class."""

    def parse_file(self, template: str) -> IntendedUsageType:
        path = DEFAULT_DIRECTORY / template
        content = path.read_text("utf-8")
        parser = IntendedUsageParser({}, {})
        return parser.parse(template, content)

    def test_check_unused(self) -> None:
        missing = {"text/rtf": "7be2577fc8b70c153e04845dc37f6a38"}
        parser = IntendedUsageParser({}, missing)
        with self.assertLogs(__script_name__, level=logging.WARNING) as context_manager:
            unused_count = parser.check_unused()
        self.assertRegex(context_manager.output[0], "text/rtf")
        self.assertEqual(len(context_manager.output), 1)
        self.assertEqual(unused_count, 1)

    def test_common(self) -> None:
        self.assertEqual(self.parse_file("audio/L8"), "Common")

    def test_common_lowercase(self) -> None:
        self.assertEqual(self.parse_file("image/vnd.fpx"), "Common")

    def test_common_not_uppercase(self) -> None:
        self.assertEqual(self.parse_file("audio/L16"), "Common")

    def test_intended_usage_without_colon(self) -> None:
        self.assertEqual(self.parse_file("application/ssml+xml"), "Common")

    def test_limited_use(self) -> None:
        self.assertEqual(self.parse_file("text/dns"), "Limited use")

    def test_limited_use_lowercase(self) -> None:
        self.assertEqual(self.parse_file("application/beep+xml"), "Limited use")

    def test_limited_use_not_uppercase(self) -> None:
        self.assertEqual(self.parse_file("text/uri-list"), "Limited use")

    def test_only_newline_separated(self) -> None:
        self.assertEqual(self.parse_file("application/mathml+xml"), "Common")

    def test_no_intended_usage_found(self) -> None:
        with self.assertRaises(NoIntendedUsageFound):
            self.parse_file("text/rtf")

    def test_no_registration_template_available(self) -> None:
        self.assertEqual(self.parse_file("text/plain"), "")

    def test_obsolete(self) -> None:
        self.assertEqual(self.parse_file("image/hsj2"), "Obsolete")

    def test_obsolete_not_uppercase(self) -> None:
        self.assertEqual(self.parse_file("application/vnd.ah-barcode"), "Obsolete")


# pylint: disable-next=too-many-public-methods
class TestDateParser(unittest.TestCase):
    # pylint: disable=missing-function-docstring
    """Test cases for DateParser class."""

    def parse_file(
        self,
        template: str,
        missing_checksum: str = "",
        rfcs: dict[int, str] | None = None,
    ) -> tuple[str, str]:
        path = DEFAULT_DIRECTORY / template
        content = path.read_text("utf-8")
        missing = {}
        if missing_checksum:
            missing[template] = missing_checksum
        parser = DateParser({}, missing, missing, rfcs or {})
        return parser.parse(template, content)

    def test_combined_created_comma_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("application/call-completion"), ("2013-02-13", "2013-04-17")
        )

    def test_combined_defined_in_rfc_comma_deprecated_by_rfc(self) -> None:
        self.assertEqual(
            self.parse_file(
                "text/directory", rfcs={2425: "1998-09", 6350: "2011-08-31"}
            ),
            ("1998-09", "2011-08-31"),
        )

    def test_combined_file_created_comma_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("application/sql"), ("2013-02-27", "2013-04-02")
        )

    def test_combined_originally_registered_by_rfc_comma_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("multipart/byteranges", rfcs={2616: "1999-06"}),
            ("1999-06", "2021-10-01"),
        )

    def test_combined_published_in_rfc_comma_last_updated_via_rfc(self) -> None:
        self.assertEqual(
            self.parse_file(
                "application/xml", rfcs={3023: "2001-01", 7303: "2014-07-07"}
            ),
            ("2001-01", "2014-04-17"),
        )

    def test_combined_registered_by_rfc_comma_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("text/csv", rfcs={4180: "2005-10-04"}),
            ("2005-10-04", "2014-01-17"),
        )

    def test_combined_registered_by_rfc_comma_optional_parameters_updated(self) -> None:
        self.assertEqual(
            self.parse_file(
                "audio/VMR-WB", rfcs={4348: "2006-01-11", 4424: "2006-02-28"}
            ),
            ("2006-01-11", "2006-02-28"),
        )

    def test_combined_registered_by_rfc_comma_optional_parameters_added(self) -> None:
        self.assertEqual(
            self.parse_file(
                "video/jpeg2000", rfcs={5371: "2008-10-21", 5372: "2008-10-21"}
            ),
            ("2008-10-21", "2008-10-21"),
        )

    def test_combined_registered_by_rfc_in_brackets_comma_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("application/merge-patch+json", rfcs={7396: "2014-10-31"}),
            ("2014-10-31", "2014-11-03"),
        )

    def test_combined_registered_by_rfc_comma_updated_by_rfc(self) -> None:
        self.assertEqual(
            self.parse_file("image/tiff", rfcs={2302: "1998-03", 3302: "2002-09-27"}),
            ("1998-03", "2002-09-27"),
        )

    def test_combined_registered_by_rfc_comma_updated_by_rfc_plus_date(self) -> None:
        self.assertEqual(
            self.parse_file(
                "audio/MP4A-LATM", rfcs={3016: "2000-11", 6416: "2011-10-18"}
            ),
            ("2000-11", "2011-10-18"),
        )

    def test_combined_registered_capitalized(self) -> None:
        self.assertEqual(
            self.parse_file("application/ld+json"), ("2013-08-16", "2020-03-17")
        )

    def test_combined_registered_comma_last_updated(self) -> None:
        self.assertEqual(self.parse_file("audio/EVS"), ("2015-12-21", "2017-12-04"))

    def test_combined_registered_comma_last_updated_obsoleted_by(self) -> None:
        self.assertEqual(
            self.parse_file("application/vnd.geo+json"), ("2014-05-20", "2016-07-07")
        )

    def test_combined_registered_comma_last_updated_see_rfc(self) -> None:
        self.assertEqual(self.parse_file("text/markdown"), ("2014-11-11", "2016-03-28"))

    def test_combined_registered_comma_updated(self) -> None:
        self.assertEqual(self.parse_file("text/html"), ("2012-09-19", "2014-05-27"))

    def test_combined_registered_comma_updated_twice(self) -> None:
        self.assertEqual(
            self.parse_file("application/x-www-form-urlencoded"),
            ("2014-05-14", "2020-07-14"),
        )

    def test_combined_registered_in_rfc_comma_updated_by_rfc(self) -> None:
        self.assertEqual(
            self.parse_file(
                "image/tiff-fx", rfcs={3250: "2002-09-25", 3950: "2005-02-09"}
            ),
            ("2002-09-25", "2005-02-09"),
        )

    def test_combined_registered_in_rfc_comma_updated_in_rfc(self) -> None:
        self.assertEqual(
            self.parse_file(
                "audio/mpa-robust", rfcs={3119: "2001-06", 5219: "2008-02-14"}
            ),
            ("2001-06", "2008-02-14"),
        )

    def test_combined_registered_in_via_rfc_comma_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("application/xhtml+xml"), ("2002-01", "2014-10-23")
        )

    def test_combined_registered_per_rfc_comma_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("application/json-seq"), ("2015-01-08", "2015-01-12")
        )

    def test_combined_registered_semicolon_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("application/mp21"), ("2009-07-07", "2009-07-07")
        )

    def test_combined_registered_through_rfc_comma_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("application/xml-patch+xml"), ("2014-07-03", "2014-07-03")
        )

    def test_combined_registered_year_comma_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("application/vnd.fujixerox.docuworks"),
            ("1998", "2019-12-03"),
        )

    def test_combined_rfc_published_subtype_last_updated(self) -> None:
        self.assertEqual(
            self.parse_file("audio/ogg", rfcs={5334: "2008-09-03"}),
            ("2008-09-03", "2016-03-07"),
        )

    def test_combined_rfc_published_subtype_last_updated_per_rfc(self) -> None:
        self.assertEqual(
            self.parse_file("audio/L8", rfcs={3555: "2003-07-29", 4856: "2007-03"}),
            ("2003-07-29", "2007-03"),
        )

    def test_combined_rfc_published_subtype_last_updated_old(self) -> None:
        self.assertEqual(
            self.parse_file("video/rtx", rfcs={4588: "2006-07-25"}),
            ("2006-07-25", "2006-07-25"),
        )

    def test_combined_rfc_published_subtype_last_updated_old_with_text(self) -> None:
        self.assertEqual(
            self.parse_file("audio/3gpp", rfcs={3839: "2004-07-13"}),
            ("2004-07-13", "2004-07-13"),
        )

    def test_combined_rfc_published_subtype_last_updated_old_with_day(self) -> None:
        self.assertEqual(
            self.parse_file("application/javascript", rfcs={4329: "2006-04-26"}),
            ("2006-04-26", "2022-05-16"),
        )

    def test_combined_rfc_published_updated(self) -> None:
        self.assertEqual(
            self.parse_file(
                "audio/EVRC", rfcs={3558: "2003-07-29", 4788: "2007-01-10"}
            ),
            ("2003-07-29", "2007-01-10"),
        )

    def test_separate_created(self) -> None:
        self.assertEqual(
            self.parse_file("image/vnd.sealed.png"), ("2003-09-09", "2003-10-02")
        )

    def test_separate_created_dash_separated_date(self) -> None:
        self.assertEqual(
            self.parse_file("text/prs.fallenstein.rst"), ("2003-10-02", "2003-10-02")
        )

    def test_separate_created_date_inverse(self) -> None:
        self.assertEqual(
            self.parse_file("application/vnd.pvi.ptid1"), ("2001-06-25", "2001-06-25")
        )

    def test_separate_created_in_square_brackets(self) -> None:
        self.assertEqual(
            self.parse_file("video/vnd.sealed.mpeg1"), ("2003-09-15", "2003-10-02")
        )

    def test_separate_created_short_month(self) -> None:
        self.assertEqual(
            self.parse_file("video/vnd.mpegurl"), ("2000-11-20", "2002-06-24")
        )

    def test_separate_email_date(self) -> None:
        self.assertEqual(
            self.parse_file("image/vnd.wap.wbmp"), ("1999-03-02", "2015-05-19")
        )

    def test_separate_deprecated_file_created(self) -> None:
        self.assertEqual(
            self.parse_file("application/vnd.gmx"), ("2008-09-19", "2009-03-04")
        )

    def test_separate_file_created_capitalized(self) -> None:
        self.assertEqual(
            self.parse_file("application/vnd.unity"), ("2007-07-03", "2007-07-03")
        )

    def test_separate_file_created_day_missing(self) -> None:
        self.assertEqual(
            self.parse_file("application/vnd.proteus.magazine"),
            ("2005-11", "2005-11-30"),
        )

    def test_separate_file_created_day_single_digit(self) -> None:
        self.assertEqual(
            self.parse_file("image/vnd.adobe.photoshop"), ("2005-12-09", "2005-12")
        )

    def test_separate_file_created_without_day(self) -> None:
        self.assertEqual(
            self.parse_file("application/vnd.vectorworks"), ("2000-02", "2009-02-19")
        )

    def test_separate_file_created_on(self) -> None:
        self.assertEqual(
            self.parse_file("application/fastinfoset"), ("2005-10-31", "2006-09-05")
        )

    def test_separate_file_updated_file_created(self) -> None:
        self.assertEqual(self.parse_file("text/jcr-cnd"), ("2012-04-03", "2012-04-03"))

    def test_separate_file_updated_file_created_old_style(self) -> None:
        self.assertEqual(
            self.parse_file("application/vnd.cups-pdf"), ("2006-08-07", "2006-08-08")
        )

    def test_separate_from_email_date(self) -> None:
        self.assertEqual(
            self.parse_file(
                "application/vnd.visio", "561862b7688985cb42a57c98e7e6a406"
            ),
            ("1997-11-03", ""),
        )

    def test_separate_last_modified(self) -> None:
        self.assertEqual(
            self.parse_file("image/png", "11e8771f6576012197948f297006fa34"),
            ("", "2021-12-07"),
        )

    def test_separate_last_updated_day_missing(self) -> None:
        self.assertEqual(
            self.parse_file("audio/vnd.cmles.radio-events"), ("2005-11-30", "2005-11")
        )

    def test_separate_last_updated_file_created(self) -> None:
        self.assertEqual(self.parse_file("text/turtle"), ("2011-03-28", "2011-03-28"))

    def test_separate_last_updated_obsoleted(self) -> None:
        self.assertEqual(
            self.parse_file("message/vnd.si.simp"), ("2007-11-20", "2012-09-19")
        )

    def test_separate_last_updated_obsolete_capitalized(self) -> None:
        self.assertEqual(
            self.parse_file("application/vnd.nokia.n-gage.symbian.install"),
            ("2007-03-12", "2007-03-12"),
        )

    def test_separate_per_rfc(self) -> None:
        self.assertEqual(
            self.parse_file(
                "text/troff", "2b9592096d599f28d710b45abbe75914", {4263: "2006-01-18"}
            ),
            ("2006-01-18", ""),
        )

    def test_separate_per_rfc_number(self) -> None:
        self.assertEqual(
            self.parse_file(
                "video/BMPEG", "86efcfb62f310455249dde88e8d2c6d8", {3555: "2003-07-29"}
            ),
            ("2003-07-29", ""),
        )

    def test_separate_per_rfc_with_space(self) -> None:
        self.assertEqual(
            self.parse_file(
                "video/H263", "5efde3497af77f73528bf23a6588514a", {3555: "2003-07-29"}
            ),
            ("2003-07-29", ""),
        )

    def test_separate_registered_by_rfc(self) -> None:
        self.assertEqual(
            self.parse_file(
                "multipart/report",
                "6b3953e176549a1d4d01a7da70aa81c9",
                {6522: "2012-01-17"},
            ),
            ("2012-01-17", ""),
        )

    def test_separate_registered_date_old(self) -> None:
        self.assertEqual(
            self.parse_file("application/samlassertion+xml"),
            ("2004-12-15", "2006-02-06"),
        )

    def test_separate_registered_in_rfc(self) -> None:
        self.assertEqual(
            self.parse_file(
                "audio/RED", "7111e393716de0818757a9cd1d1737a1", {3555: "2003-07-29"}
            ),
            ("2003-07-29", ""),
        )

    def test_separate_registered_via_rfc(self) -> None:
        self.assertEqual(
            self.parse_file(
                "audio/opus", "27f87d963a3ba3880460bff97f2ea6ec", {7587: "2015-06-30"}
            ),
            ("2015-06-30", ""),
        )

    def test_separate_rfc_published_subtype_last_updated_per_rfc(self) -> None:
        self.assertEqual(
            self.parse_file("application/jose", "2dcfc71032928f03f5f4ea5db0a94ce4"),
            ("2015-01-23", ""),
        )

    def test_separate_rfc_published(self) -> None:
        self.assertEqual(
            self.parse_file(
                "audio/MPA",
                "99eb3f463ca236d6d98a543739ea82bc",
                rfcs={3555: "2003-07-29"},
            ),
            ("2003-07-29", ""),
        )

    def test_separate_sent_email(self) -> None:
        self.assertEqual(
            self.parse_file("text/vnd.fly", "5021b2c888bbaec8c03758cf7df3062a"),
            ("1999-08-12", ""),
        )

    def test_separate_submitted_to_iana(self) -> None:
        self.assertEqual(self.parse_file("image/vnd.fpx"), ("1996-09-09", "2009-04-07"))


class TestMain(unittest.TestCase):
    """Test cases for main function."""

    def test_no_stack_trace(self) -> None:
        """Test that the main function does not crash."""
        main([__script_name__])


if __name__ == "__main__":
    sys.exit(main(sys.argv))  # pragma: no cover
