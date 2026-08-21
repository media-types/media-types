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

## 3. Generate mime.types

As last step, generate `mime.types` from the enhanced IANA CSV file.
Media types can be excluded from the output file
to support removing deprecated or obsoleted media types.
A (different) header and a footer can be added to `mime.types`.

Building
========

1. Ensure `make` and Python 3 are installed.
2. Run `make`.

To build a website with this generated data in a directory named `_site`, run `make site`.

Installing
==========

Run `make install` to install `mime.types` to `/etc/mime.types`
and the enhanced IANA CSV file to `/usr/share/media-types`.

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

To exclude additional media types from `mime.types`,
create a CSV file with at least the column `Media Type`.
Set the environment/make variable `EXTRA_EXCLUDE` to its path.
Example content:

```csv
Media Type,Reason
image/hsj2,Because I said so
```

To add a different header to `mime.types`
set the environment/make variable `HEADER` to a file containing it.
To add a footer to `mime.types`
set the environment/make variable `FOOTER` to a file containing it.

Related projects
================

These projects serve a similar purpose:

* **[FreeDesktop.org Shared MIME Info Specification](https://www.freedesktop.org/wiki/Specifications/shared-mime-info-spec/)**
  defines an extensible XML-based database. The core database is provided by
  **[shared-mime-info](https://www.freedesktop.org/wiki/Software/shared-mime-info/)**.
  Other projects can register additional mime types.
  Desktop environments like GNOME, KDE, ROX, and Xfce use this database.

* **[mime-types/mime-types-data](https://github.com/mime-types/mime-types-data)**
  is a MIME media type definition registry
  used to map file extensions to their corresponding MIME types and vice versa.
  The data is sourced from various registries and user contributions.
  It is provided in different formats (YAML, JSON, etc.) and used primarily in Ruby.
  The project is active and releases multiple times per year.

* **[jshttp/mime-db](https://github.com/jshttp/mime-db)**
  is a large database of mime types and information about them.
  It consists of a single, public JSON file and does not include any logic.
  It aggregates data from IANA, Apache httpd, and NGINX.
  There was only one release in 2025 and one in 2024.

* The **[file(1)](https://github.com/file/file)** command and the `libmagic(3)` library
  identify thousands of file types and their corresponding MIME types by looking
  for 'magic numbers'.

These projects provide their own registry:

* **Apache httpd**: [docs/conf/mime.types](https://github.com/apache/httpd/blob/trunk/docs/conf/mime.types)
  ([SVN repo](https://svn.apache.org/repos/asf/httpd/httpd/trunk/docs/conf/mime.types))

* **Apache Tika**:
  [tika-core/src/main/resources/org/apache/tika/mime/tika-mimetypes.xml](https://github.com/apache/tika/blob/main/tika-core/src/main/resources/org/apache/tika/mime/tika-mimetypes.xml)

* **[Mailcap](https://github.com/InfrastructureServices/mailcap)**:
  [mime.types](https://github.com/InfrastructureServices/mailcap/blob/master/mime.types)
  is synced with IANA from time to time (but no update between May 2023 and August 2026).

* **NGINX**: [conf/mime.types](https://github.com/nginx/nginx/blob/master/conf/mime.types)
  contains a quite short list and the config format is specific for NGINX.

* **Python Standard Library**:
  [Lib/mimetypes.py](https://github.com/python/cpython/blob/main/Lib/mimetypes.py)
  includes a minimal default set, but primarily parses local system `mime.types` files.

Creating releases
=================

This project uses [calendar versioning](https://calver.org/) in the form
`YYYY.0M.0D`. To create a release, increase the version in [Makefile](Makefile)
and document the noteworthy changes in [NEWS.md](./NEWS.md).
Then commit the changes, tag the release, and generate a xz-compressed release
tarball:

```
version=$(make version)
git commit -sm "Release media-types $version" Makefile NEWS.md
git tag -a "v$version" -m "Release media-types $version"
make dist
```
