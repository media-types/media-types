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

"""Generate IANA CSV file with additional file extensions column."""

import argparse
import csv
import dataclasses
import hashlib
import logging
import os
import pathlib
import re
import sys
import unittest
from collections.abc import Iterator
from typing import Self

from media_types import (
    MediaType,
    MediaTypeList,
    ParserFailure,
    get_top_level_media_type_names,
    parse_space_separated_list,
)

DEFAULT_FILE_EXTENSIONS_MANUAL = pathlib.Path("parser/file_extensions/manual.csv")
DEFAULT_FILE_EXTENSIONS_MAPPING = pathlib.Path("parser/file_extensions/mapping.tsv")
DEFAULT_FILE_EXTENSIONS_MISSING = pathlib.Path("parser/file_extensions/missing.csv")
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


class NoFileExtensionsFound(ParserFailure):
    """Raised when no file extensions where found."""


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


def blake2b_128bit(text: str) -> str:
    """Calculates the 128-bit (32-hex-character) BLAKE2b hash of a string."""
    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()


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


def load_file_extensions_manual(path: pathlib.Path) -> dict[str, ManualFileExtensions]:
    """Load file extensions manual CSV file."""
    mapping = {}
    for row in iter_csv_rows(path):
        value = ManualFileExtensions.from_csv_dict(row)
        mapping[value.media_type] = value
    return mapping


def load_file_extensions_mapping(path: pathlib.Path) -> dict[str, list[str]]:
    """Load file extensions mapping tab-separated value file."""
    mapping = {}
    for line in iter_non_comment_lines(path):
        extensions_str, key = line.split("\t")
        mapping[key] = parse_space_separated_list(extensions_str)
    return mapping


def load_file_extensions_missing(path: pathlib.Path) -> dict[str, str]:
    """Load file extensions mapping tab-separated value file."""
    mapping = {}
    for row in iter_csv_rows(path):
        mapping[row["Media Type"]] = row["BLAKE2b Checksum"]
    return mapping


def _strip(text: str) -> str:
    if text.startswith("'") and text.endswith("'"):
        text = text[1:-1]
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    return text.removeprefix(".").removeprefix("*.")


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
        missing = load_file_extensions_missing(missing_file)
        return cls(manual, mapping, missing)

    # pylint: disable-next=too-many-return-statements
    def parse(self, template: str, content: str) -> list[str]:
        """Extract file extensions from template text content."""
        if content.strip() == "No registration template available.":
            return []

        if template in self.manual:
            checksum = blake2b_128bit(content)
            if checksum != self.manual[template].checksum:
                raise ChecksumMismatch(
                    template, self.manual[template].checksum, checksum
                )
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
                checksum = blake2b_128bit(content)
                if checksum != self.missing[template]:
                    raise ChecksumMismatch(template, self.missing[template], checksum)
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


def iter_media_types(directory: pathlib.Path) -> Iterator[MediaType]:
    """Iterate over media types loaded from CSV files in a directory."""
    for top_level_media_type in get_top_level_media_type_names(directory):
        path = directory / f"{top_level_media_type}.csv"
        for row in iter_csv_rows(path):
            yield MediaType(row["Name"], row["Template"], [], row["Reference"])


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser()
    # pylint: disable-next=duplicate-code
    parser.add_argument(
        "-d",
        "--directory",
        default=pathlib.Path("iana"),
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
    return parser.parse_args()


def main() -> int:
    """Generate IANA CSV file with additional file extensions column."""
    args = parse_args()
    logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)

    parser = FileExtensionsParser.from_files(
        args.file_extensions_manual,
        args.file_extensions_mapping,
        args.file_extensions_missing,
    )
    media_types = MediaTypeList(iter_media_types(args.directory))
    failures = media_types.add_additional_information(parser.parse, args.directory)
    parser.check_unused()
    media_types.write_to_csv(args.output)
    return failures


# pylint: disable-next=too-many-public-methods
class TestFileExtensionsParser(unittest.TestCase):
    # pylint: disable=missing-function-docstring
    """Test cases for FileExtensionsParser class."""

    IANA_DIR = pathlib.Path("iana")

    def parse_file(self, template: str) -> list[str] | None:
        path = self.IANA_DIR / template
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

    def test_parse_full(self) -> None:
        parser = FileExtensionsParser.from_files(
            DEFAULT_FILE_EXTENSIONS_MANUAL,
            DEFAULT_FILE_EXTENSIONS_MAPPING,
            DEFAULT_FILE_EXTENSIONS_MISSING,
        )
        media_types = MediaTypeList(iter_media_types(self.IANA_DIR))
        self.assertEqual(
            media_types.add_additional_information(parser.parse, self.IANA_DIR), 0
        )
        self.assertEqual(parser.check_unused(), 0)


if __name__ == "__main__":
    sys.exit(main())
