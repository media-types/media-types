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

"""Render website html pages from Jinja 2 template and CSV files."""

import argparse
import pathlib
from typing import Any

import jinja2

from media_types import EnhancedMediaTypeList, MediaType, MediaTypeList

TEMPLATE_DIRECTORY = "website"


def _render_html_pages(context: dict[str, Any], output_dir: pathlib.Path) -> None:
    output_dir.mkdir(exist_ok=True)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIRECTORY))
    for template_name in env.list_templates(
        filter_func=lambda name: name.endswith(".jinja2")
    ):
        template = env.get_template(template_name)
        rendered = template.render(context)

        output_path = output_dir / template_name.removesuffix(".jinja2")
        output_path.write_text(rendered)


def main() -> None:
    """Render index.html from Jinja 2 template and CSV files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-m",
        "--media-types-csv",
        default=pathlib.Path("media-types.csv"),
        type=pathlib.Path,
    )
    parser.add_argument(
        "--mime-types", default=pathlib.Path("mime.types"), type=pathlib.Path
    )
    parser.add_argument(
        "-i", "--iana-csv", default=pathlib.Path("iana.csv"), type=pathlib.Path
    )
    parser.add_argument(
        "-o", "--output", default=pathlib.Path("_site"), type=pathlib.Path
    )
    args = parser.parse_args()

    media_types = EnhancedMediaTypeList.from_files([args.media_types_csv])
    mime_types = args.mime_types.read_text("utf-8")
    iana: MediaTypeList[MediaType] = MediaTypeList.from_files([args.iana_csv])
    context = {"media_types": media_types, "mime_types": mime_types, "iana": iana}
    _render_html_pages(context, args.output)


if __name__ == "__main__":
    main()
