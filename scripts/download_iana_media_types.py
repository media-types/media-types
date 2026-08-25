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

"""Download and update IANA media type CSV assignments and templates."""

import argparse
import concurrent.futures
import json
import logging
import os
import pathlib
import random
import sys
import threading
import time
import types
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator, Sequence
from typing import Self

from media_types import (
    ALLOWED_MISSING_TEMPLATES,
    TOP_LEVEL_TYPES_CSV,
    get_top_level_media_type_names,
    iter_csv_rows,
)

ATTEMPTS = 3
BASE_DELAY = 10.0
MIN_DELAY = 1.0
BASE_URL = "https://www.iana.org/assignments"
CACHE_FILENAME = "last-modified.json"
DEFAULT_WORKERS = 16
MEDIA_TYPES_URL = f"{BASE_URL}/media-types"
EXPECT_MISSING = {f"{MEDIA_TYPES_URL}/{t}" for t in ALLOWED_MISSING_TEMPLATES}
LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s: %(message)s"
__script_name__ = os.path.basename(sys.argv[0]) if __name__ == "__main__" else __name__


class LastModifiedCache:
    """Thread-safe manager for persistent HTTP Last-Modified headers."""

    def __init__(self, cache_directory: pathlib.Path) -> None:
        self.cache_path = cache_directory / CACHE_FILENAME
        self._lock = threading.Lock()
        self._cache: dict[str, str] = self.load()

    def load(self) -> dict[str, str]:
        """Load the cache content from disk."""
        if not self.cache_path.exists():
            return {}
        try:
            with self.cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, dict), "Cache content is not a dict"
            assert all(
                isinstance(k, str) and isinstance(v, str) for k, v in data.items()
            ), "Cache entries must be string key-value pairs"
            return data
        except (AssertionError, json.JSONDecodeError, OSError) as error:
            logger = logging.getLogger(__script_name__)
            logger.warning("Failed to load cache '%s': %s", self.cache_path, error)
            return {}

    def save(self) -> None:
        """Save the cache contents to disk."""
        with self._lock:
            try:
                self.cache_path.parent.mkdir(exist_ok=True)
                with self.cache_path.open("w", encoding="utf-8") as f:
                    json.dump(self._cache, f, indent=2, sort_keys=True)
                    f.write(os.linesep)
            except OSError as error:
                logger = logging.getLogger(__script_name__)
                logger.error("Failed to save cache to '%s': %s", self.cache_path, error)

    def get_last_modified(self, url: str) -> str | None:
        """Return the cached Last-Modified header string for a URL if present."""
        with self._lock:
            return self._cache.get(url)

    def set_last_modified(self, url: str, last_modified: str | None) -> None:
        """Update or set the Last-Modified header for a URL."""
        with self._lock:
            if last_modified is None:
                self._cache.pop(url, None)
            else:
                self._cache[url] = last_modified

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.save()


def _strip_trailing_whitespace(text: str) -> str:
    stripped = "\n".join(l.rstrip() for l in text.splitlines())
    return stripped.rstrip() + os.linesep


def _handle_http_error(
    error: urllib.error.HTTPError, url: str, attempt: int, attempts: int
) -> bool:
    """Process HTTP errors and determine whether to retry."""
    logger = logging.getLogger(__script_name__)

    retry_after = error.headers.get("Retry-After")
    if retry_after and retry_after.isdigit():
        wait_time = float(retry_after)
    elif error.code in (429, 500, 502, 503, 504, 520):
        delay = BASE_DELAY * (2**attempt)
        wait_time = random.uniform(MIN_DELAY, delay)
    else:
        wait_time = 0.0

    attempt_str = ""
    if attempts > 1:
        attempt_str = f" (attempt {attempt + 1}/{attempts})"

    if wait_time and attempt + 1 < attempts:
        logger.warning(
            "HTTP %s (%s) for '%s'. Retrying in %.1f seconds%s...",
            error.code,
            error.reason,
            url,
            wait_time,
            attempt_str,
        )
        time.sleep(wait_time)
        return True

    logger.error(
        "HTTP %s (%s) for '%s'%s%s",
        error.code,
        error.reason,
        url,
        attempt_str,
        ". Waiting %.1f seconds..." if wait_time else "",
    )
    if wait_time:
        time.sleep(wait_time)
    return False


def download_file(
    url: str, path: pathlib.Path, cache: LastModifiedCache, attempts: int = ATTEMPTS
) -> int:
    """Download a file from a URL and save it if the content has changed.

    Return failure count."""
    request = urllib.request.Request(url)
    try:
        previous_content = path.read_text("utf-8")
        last_modified = cache.get_last_modified(url)
        if last_modified:
            request.add_header("If-Modified-Since", last_modified)
    except FileNotFoundError:
        previous_content = ""
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request) as response:
                encoding = response.headers.get_content_charset() or "utf-8"
                content = _strip_trailing_whitespace(response.read().decode(encoding))
            if content != previous_content:
                path.parent.mkdir(exist_ok=True)
                path.write_text(content, "utf-8")
                logger = logging.getLogger(__script_name__)
                logger.info("Updated content for '%s' (%d bytes).", path, len(content))
            cache.set_last_modified(url, response.headers.get("Last-Modified"))
            return 0
        except urllib.error.HTTPError as error:
            if error.code == 304:
                return 0
            logger = logging.getLogger(__script_name__)
            if url in EXPECT_MISSING and error.code == 404:
                logger.info("As expected '%s' was not found.", url)
                return 0
            if _handle_http_error(error, url, attempt, attempts):
                continue
            break
        except urllib.error.URLError as error:
            logger = logging.getLogger(__script_name__)
            logger.error("Network error while downloading '%s': %s", path, error.reason)
            break
        except OSError as error:
            logger = logging.getLogger(__script_name__)
            logger.error("File system error writing to '%s': %s", path, error)
            break
    return 1


def download_files_in_parallel(
    tasks: list[tuple[str, pathlib.Path]], cache: LastModifiedCache, max_workers: int
) -> int:
    """Execute a list of (url, path) download tasks concurrently using threads."""
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(download_file, url, path, cache) for url, path in tasks
        ]
        try:
            for future in concurrent.futures.as_completed(futures):
                failures += future.result()
        except KeyboardInterrupt:
            executor.shutdown(wait=False, cancel_futures=True)
            raise
    return failures


def download_media_types(
    top_level_media_type_names: Sequence[str],
    directory: pathlib.Path,
    cache: LastModifiedCache,
    max_workers: int,
) -> int:
    """Download media type CSV files for each specified top-level media type."""
    logger = logging.getLogger(__script_name__)
    logger.info(
        "Downloading %i media type CSV files...", len(top_level_media_type_names)
    )
    tasks = [
        (f"{MEDIA_TYPES_URL}/{media_type}.csv", directory / f"{media_type}.csv")
        for media_type in top_level_media_type_names
    ]
    return download_files_in_parallel(tasks, cache, max_workers)


def download_templates_from_file(
    media_type_file: pathlib.Path,
    directory: pathlib.Path,
    cache: LastModifiedCache,
    max_workers: int,
) -> int:
    """Download all media type template files listed inside a given media type CSV."""
    logger = logging.getLogger(__script_name__)
    templates = list(read_templates(media_type_file))
    logger.info(
        "Downloading %i media type template files for %s...",
        len(templates),
        media_type_file,
    )
    tasks = [
        (f"{MEDIA_TYPES_URL}/{template}", directory / template)
        for template in templates
    ]
    return download_files_in_parallel(tasks, cache, max_workers)


def download_templates(
    top_level_media_type_names: Iterable[str],
    directory: pathlib.Path,
    cache: LastModifiedCache,
    max_workers: int,
) -> int:
    """Download template files for all provided top-level media types."""
    failures = 0
    for media_type in top_level_media_type_names:
        failures += download_templates_from_file(
            directory / f"{media_type}.csv", directory, cache, max_workers
        )
    return failures


def download_top_level_media_type_names(
    directory: pathlib.Path, cache: LastModifiedCache
) -> int:
    """Download the main top-level media types CSV file from IANA."""
    logger = logging.getLogger(__script_name__)
    logger.info("Downloading top-level media types CSV...")
    url = f"{BASE_URL}/top-level-media-types/{TOP_LEVEL_TYPES_CSV}"
    path = directory / TOP_LEVEL_TYPES_CSV
    return download_file(url, path, cache)


def read_templates(path: pathlib.Path) -> Iterator[str]:
    """Read a media type CSV file and yield template file relative paths."""
    for row in iter_csv_rows(path):
        yield row["Template"]


def main() -> int:
    """Parse CLI arguments and download IANA media type definitions and templates."""
    start_time = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-d",
        "--directory",
        default=pathlib.Path("iana"),
        type=pathlib.Path,
        help="directory to store downloaded IANA files (default: %(default)s)",
    )
    parser.add_argument(
        "-w",
        "--workers",
        default=DEFAULT_WORKERS,
        type=int,
        help="number of worker threads for parallel downloads (default: %(default)s)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        dest="log_level",
        action="store_const",
        const=logging.ERROR,
        default=logging.INFO,
        help="Do not write anything to standard error except errors.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format=LOG_FORMAT)
    logger = logging.getLogger(__script_name__)

    failures = 0
    with LastModifiedCache(args.directory) as cache:
        failures += download_top_level_media_type_names(args.directory, cache)
        top_level_media_type_names = list(
            get_top_level_media_type_names(args.directory)
        )
        failures += download_media_types(
            top_level_media_type_names, args.directory, cache, args.workers
        )
        failures += download_templates(
            top_level_media_type_names, args.directory, cache, args.workers
        )

    elapsed_time = time.perf_counter() - start_time
    logger.info("Completed execution in %.2f seconds.", elapsed_time)
    return failures


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logging.getLogger(__script_name__).info("Execution interrupted by user.")
        sys.exit(130)
