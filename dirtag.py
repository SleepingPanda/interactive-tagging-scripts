#!/usr/bin/env python3

# Batch-tag manga CBZ files with ComicTagger using a JSON formatted metadata file.

# Metadata file layout:
#     {"Manga": {"<series directory name>": {...series fields...}}}

# Usage:
#     dirtag.py                          # interactive mode
#     dirtag.py -a                       # tag every series subdirectory
#     dirtag.py -a -r                    # only files modified in the last 14 days
#     dirtag.py -m meta.json -d /library


from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

RECENT_DAYS = 14
DEFAULT_METADATA = Path("manga.json")
ISSUE_SENTINEL = -100_000
OWNER_UID = 1000
OWNER_GID = 1000
FILE_MODE = 0o644

VOLUME_RE = re.compile(r"\bv(?:ol\.?\s*)?(\d+)\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\((\d{4})\)")
TEXT_FIELDS = ("language", "genre", "maturity_rating", "publisher", "imprint", "series", "series_group", "web_link")

log = logging.getLogger("dirtag")

USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
LEVEL_CODES = {"DEBUG": "36", "INFO": "36", "WARNING": "33", "ERROR": "31", "CRITICAL": "31"}


# Wrap *text* in an ANSI SGR code, or return it unchanged if colors are off.
def paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


# Log formatter that colors the level tag by severity.
class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        label = paint(f"[{record.levelname}]", LEVEL_CODES.get(record.levelname, "0"))
        return f"{label} {record.getMessage()}"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

# Return the volume number in a filename such as 'v01' or 'Vol.2', or None.
def parse_volume(filename: str) -> int | None:
    match = VOLUME_RE.search(filename)
    if match:
        return int(match.group(1))
    log.warning("Could not extract volume number from '%s'.", filename)
    return None


# Return the year in a filename such as '(2023)', or None.
def parse_year(filename: str) -> int | None:
    match = YEAR_RE.search(filename)
    if match:
        return int(match.group(1))
    log.warning("Could not extract year from '%s'.", filename)
    return None


# Escape ',' and '=' which ComicTagger treats as delimiters.
def _esc(value: Any) -> str:
    return str(value).replace(",", "^,").replace("=", "^=")


def _yn(flag: bool) -> str:
    return "Yes" if flag else "No"


# Build the comma-delimited key=value string for `comictagger -m`.
def build_metadata_string(meta: dict, volume: int | None = None, year: int | None = None) -> str:
    parts = [
        f"manga={_yn(meta.get('manga', False))}",
        f"issue={ISSUE_SENTINEL}",
        f"black_and_white={_yn(meta.get('black_and_white', False))}",
    ]
    parts += [f"{key}={_esc(meta.get(key, ''))}" for key in TEXT_FIELDS]
    if volume is not None:
        parts += [f"volume={volume}", f"title=Volume {volume}"]
    if year is not None:
        parts.append(f"year={year}")

    for role, person in meta.get("credit", {}).items():
        parts.append(f"credit={role}:{_esc(person)}")
    characters = meta.get("characters", [])
    if characters:
        parts.append("characters=" + "^,".join(_esc(c) for c in characters))

    return ",".join(parts)


# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------

# Recursively list .cbz files, optionally limited to recently modified ones.
def find_cbz(directory: Path, recent_only: bool) -> list[Path]:
    cutoff = time.time() - RECENT_DAYS * 86_400
    return [
        p for p in directory.rglob("*.cbz")
        if not recent_only or p.stat().st_mtime >= cutoff
    ]


# Chown the series directory tree and chmod its .cbz files. No-op on Windows.
def fix_permissions(directory: Path) -> None:
    if os.name == "nt":
        return
    try:
        for root, dirs, files in os.walk(directory):
            for name in dirs + files:
                os.chown(os.path.join(root, name), OWNER_UID, OWNER_GID)
            for name in files:
                if name.lower().endswith(".cbz"):
                    os.chmod(os.path.join(root, name), FILE_MODE)
        os.chown(directory, OWNER_UID, OWNER_GID)
    except OSError as exc:
        log.warning("Permission update failed for '%s': %s", directory, exc)


# ---------------------------------------------------------------------------
# Tagging
# ---------------------------------------------------------------------------

# Run ComicTagger on each file, deriving volume and year from its name.
def tag_files(files: list[Path], meta: dict) -> None:
    for cbz in files:
        volume = parse_volume(cbz.name)
        year = parse_year(cbz.name)
        command = [
            "comictagger",
            "-R",            # required even for a single file
            "-s",            # save tags
            "-t", "cr",      # ComicRack tag format
            "--overwrite",
            "--nosummary",
            "-m", build_metadata_string(meta, volume, year),
            str(cbz),
        ]
        log.debug("Tagging '%s' (volume=%s, year=%s).", cbz.name, volume, year)
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as exc:
            log.error("ComicTagger failed for '%s': %s", cbz.name, exc)


# Tag all .cbz files in one series directory, matched by directory name.
def process_series(directory: Path, book: dict[str, dict], recent_only: bool, perms: bool) -> None:
    meta = book.get(directory.name)
    if meta is None:
        log.warning("No metadata entry for '%s'. Skipping.", directory.name)
        return
    files = find_cbz(directory, recent_only)
    if not files:
        log.info("No .cbz files found in '%s'.", directory)
        return
    tag_files(files, meta)
    if perms:
        fix_permissions(directory)
    log.info("Finished '%s' (%d file(s)).", directory.name, len(files))


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

# Prompt until the user picks a directory number or enters 'q'.
def choose_directory(dirs: list[Path]) -> Path | None:
    while True:
        print(paint("Available directories:", "33"))
        for i, d in enumerate(dirs, start=1):
            print(f"  {paint(str(i) + '.', '31')} {paint(d.name, '32')}")
        raw = input(paint("Choose a directory # or 'q' to quit: ", "31")).strip().lower()
        if raw == "q":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(dirs):
            return dirs[int(raw) - 1]
        print(paint(f"Invalid choice. Enter a number from 1 to {len(dirs)}, or 'q'.", "31"))


def ask_yes_no(question: str) -> bool:
    return input(paint(f"{question} (y/n): ", "31")).strip().lower().startswith("y")


def run_interactive(subdirs: list[Path], book: dict[str, dict], perms: bool) -> None:
    try:
        while (selected := choose_directory(subdirs)) is not None:
            recent = ask_yes_no(f"Process only recent files in '{selected.name}'?")
            process_series(selected, book, recent, perms)
    except (KeyboardInterrupt, EOFError):
        print()
    log.info("Finished manual processing.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Load the 'Manga' section of the metadata JSON, exiting with a message on error.
def load_metadata(path: Path) -> dict[str, dict]:
    if not path.is_file():
        sys.exit(f"Metadata file '{path}' not found.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"Failed to parse '{path}': {exc}")
    manga = data.get("Manga") if isinstance(data, dict) else None
    if not isinstance(manga, dict):
        sys.exit(f"'{path}' is missing a top-level 'Manga' object.")
    return manga


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Batch tag manga CBZ files with ComicTagger.")
    p.add_argument("-m", "--metadata", type=Path, default=DEFAULT_METADATA,
                   help=f"Metadata JSON path (default: {DEFAULT_METADATA}).")
    p.add_argument("-d", "--directory", type=Path, default=Path("."),
                   help="Root directory containing series subdirectories (default: .).")
    p.add_argument("-r", "--recent", action="store_true",
                   help=f"Only process .cbz files modified in the last {RECENT_DAYS} days.")
    p.add_argument("-a", "--all", action="store_true",
                   help="Process every subdirectory without prompting.")
    p.add_argument("--no-perms", action="store_true",
                   help="Skip chown/chmod after tagging.")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG output.")
    return p


def main() -> None:
    args = build_parser().parse_args()
    if os.name == "nt":
        os.system("")  # enables ANSI escape handling in older Windows consoles
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, handlers=[handler])
    if shutil.which("comictagger") is None:
        sys.exit("'comictagger' was not found on PATH.")
    if not args.directory.is_dir():
        sys.exit(f"Directory '{args.directory}' does not exist.")
    book = load_metadata(args.metadata)
    subdirs = sorted(p for p in args.directory.iterdir() if p.is_dir())
    if not subdirs:
        sys.exit(f"No subdirectories found in '{args.directory}'.")
    perms = not args.no_perms
    if args.all:
        for d in subdirs:
            process_series(d, book, args.recent, perms)
        log.info("Finished processing all directories.")
    else:
        run_interactive(subdirs, book, perms)


if __name__ == "__main__":
    main()