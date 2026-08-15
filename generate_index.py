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

"""Render index.html from Jinja 2 template and CSV files."""

import argparse
import pathlib
from typing import Any

import jinja2

from media_types import MediaTypeList

TEMPLATE_DIRECTORY = "website"
TEMPLATE = "index.html.jinja2"


def _render_index_html(context: dict[str, Any], output: pathlib.Path) -> None:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIRECTORY))
    template = env.get_template(TEMPLATE)
    rendered = template.render(context)

    output.parent.mkdir(exist_ok=True)
    output.write_text(rendered)


def main() -> None:
    """Render index.html from Jinja 2 template and CSV files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-i", "--iana-csv", default=pathlib.Path("iana.csv"), type=pathlib.Path
    )
    parser.add_argument(
        "-o", "--output", default=pathlib.Path("_site/index.html"), type=pathlib.Path
    )
    args = parser.parse_args()

    iana = MediaTypeList.from_files([args.iana_csv])
    context = {"iana": iana}
    _render_index_html(context, args.output)


if __name__ == "__main__":
    main()
