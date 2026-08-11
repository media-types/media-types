Media Types
===========

This project contains the media type information provided by the Internet
Assigned Numbers Authority (IANA) on the
[IANA Media Types Registry](https://www.iana.org/assignments/media-types/).

Data Pipeline
=============

## 1. Add "File Extensions" column

The [IANA Media Types Registry](https://www.iana.org/assignments/media-types/)
provides CSV tables containing Name, Template, and Reference.
It also links to individual media type templates that include additional information,
such as file extensions and magic numbers.
Unfortunately, these template files are plain text with varying structures
(though recent entries follow a standardized layout) and non-standardized value formats.

As a first step, these template files are parsed to extract the file extensions data.
A new CSV table is then generated featuring the added "File Extensions" column.

Ideally, the IANA Media Types Registry would provide this information directly.

Building
========

1. Ensure `make` and Python 3 are installed.
2. Run `make`.

To build a website with this generated data in a directory named `_site`, run `make site`.
