Media Types
===========

This project contains the media type information provided by the Internet
Assigned Numbers Authority (IANA) on the
[IANA Media Types Registry](https://www.iana.org/assignments/media-types/).

The latest generated data can be found on https://media-types.github.io.

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

## 2. Enhance IANA data with "Unique File Extensions" column

As a second step,
the IANA CSV table is enhanced with a new "Unique File Extensions" column.
Following rules are applied:

* Uppercase file extensions (mentioned in a config file) are converted to lowercase.
* Duplicate file extensions (i.e. file extensions that are mentioned by two or more media types)
  can either be resolved by picking a preferred media type (configured via a config file)
  or by removed them from all media types.

This step can be heavily modified by users:

* Additional (non IANA) media types can be added
* Additional file extensions can be specified for media types

Building
========

1. Ensure `make` and Python 3 are installed.
2. Run `make`.

To build a website with this generated data in a directory named `_site`, run `make site`.

Installing
==========

Run `make install` to install the enhanced IANA CSV file to `/usr/share/media-types`.

Modification
============

To add additional media types,
create a CSV file with at least the columns `Template` and `File Extensions`.
Set the environment/make variable `EXTRA_MEDIA_TYPES` to its path.
Example content:

```csv
Name,Template,File Extensions,Reference
LilyPond,text/x-lilypond,ly,https://lilypond.org
```

To add additional file extensions to already existing media types,
create a CSV file with at least the columns `Template` and `File Extensions`.
Set the environment/make variable `EXTRA_FILE_EXTENSIONS` to its path.

Example content:

```csv
Template,File Extensions
application/pgp-keys,key
audio/mp4,m4a
image/tiff,tiff
```

The additional media types and/or file extensions can cause
more file extensions being mentioned by two or more media types.
In this case add those file extensions to a file to acknowledge them.
Set the environment/make variable `EXTRA_KNOWN_DUPLICATES` to its path.
Example content:

```
# List of file extensions that are mentioned by two or more media types
key
```

To resolve duplicate file extensions, pick a preferred media type for them.
Create a CSV file with at least the columns `File Extension` and `Media Type`.
Set the environment/make variable `EXTRA_UNIQUE_FILE_EXTENSIONS` to its path.
Example content:

```csv
File Extension,Media Type
img,
key,application/pgp-keys
```

**Note**: To removed a file extension from all media types, set the media type to an empty string.
