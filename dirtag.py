#!/usr/bin/env python3
"""dirtag.py — Batch-tag manga CBZ files using ComicTagger and a JSON metadata file.

Usage examples:
    python dirtag.py                          # interactive mode
    python dirtag.py -a                       # tag all subdirectories automatically
    python dirtag.py -a -r                    # tag only recently modified files
    python dirtag.py -m my_metadata.json -d /path/to/manga
"""

import argparse
import json
import logging
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from colorama import Fore, init

# Initialise colorama so ANSI colour codes are reset after each print.
init(autoreset=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Number of days used to define "recent" when --recent is passed.
RECENT_DAYS: int = 14

#: Default path to the JSON file that contains per-series metadata.
DEFAULT_METADATA_FILE: str = "manga.json"

#: ComicTagger uses -100 000 as a sentinel that means "not a numbered issue".
COMICTAGGER_VOLUME_SENTINEL: int = -100_000

FILE_OWNER: str = "1000:1001"
FILE_MODE: str = "644"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class SeriesMetadata(TypedDict, total=False):
    manga: bool
    black_and_white: bool
    language: str
    genre: str
    maturity_rating: str
    publisher: str
    imprint: str
    series: str
    series_group: str
    web_link: str
    characters: List[str]
    credit: Dict[str, str]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool) -> None:
    """Configure the root logger.

    Args:
        verbose: When True, emit DEBUG messages in addition to INFO and above.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=f"{Fore.CYAN}[%(levelname)s]{Fore.RESET} %(message)s",
    )


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------

def list_subdirectories(parent: Path) -> List[Path]:
    """Return a sorted list of immediate subdirectories inside *parent*.

    Args:
        parent: The directory to inspect.

    Returns:
        Sorted list of :class:`Path` objects, one per subdirectory.
        Returns an empty list (and logs an error) if *parent* does not exist.
    """
    if not parent.exists():
        logging.error(f"Directory '{parent}' does not exist.")
        return []
    return sorted(d for d in parent.iterdir() if d.is_dir())


def get_cbz_files(directory: Path, recent_only: bool = False, days: int = RECENT_DAYS) -> List[Path]:
    """Recursively find all .cbz files inside *directory*.

    Args:
        directory:   Root directory to search.
        recent_only: When True, only return files modified within the last *days* days.
        days:        Age threshold (in days) used when *recent_only* is True.

    Returns:
        List of matching :class:`Path` objects.
    """
    cutoff_mtime = time.time() - days * 86_400 if recent_only else 0.0
    return [
        f for f in directory.rglob("*.cbz")
        if not recent_only or f.stat().st_mtime >= cutoff_mtime
    ]


# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------

def extract_volume_number(filename: str) -> Optional[int]:
    """Parse a volume number from a CBZ filename.

    Recognises patterns such as ``v01``, ``v1``, ``Vol.2``, ``Vol 03``.

    Args:
        filename: Bare filename (not a full path) of the CBZ file.

    Returns:
        The volume number as an integer, or ``None`` if no match was found.
    """
    match = re.search(r"[Vv](?:ol\.?\s*)?(\d+)", filename)
    if match:
        return int(match.group(1))
    logging.warning(f"Could not extract volume number from '{filename}'.")
    return None


def extract_publication_year(filename: str) -> Optional[int]:
    """Parse a four-digit publication year from a CBZ filename.

    Expects the year to be wrapped in parentheses, e.g. ``(2023)``.

    Args:
        filename: Bare filename (not a full path) of the CBZ file.

    Returns:
        The year as an integer, or ``None`` if no match was found.
    """
    match = re.search(r"\((\d{4})\)", filename)
    if match:
        return int(match.group(1))
    logging.warning(f"Could not extract year from '{filename}'.")
    return None


# ---------------------------------------------------------------------------
# Metadata formatting
# ---------------------------------------------------------------------------

def _escape(value: Any) -> str:
    """Escape characters that ComicTagger treats as delimiters.

    ComicTagger uses ``,`` as a field separator and ``=`` as a key/value
    separator.  Literal occurrences of these characters inside a value must
    be escaped with a preceding ``^``.

    Args:
        value: The raw metadata value (will be coerced to ``str``).

    Returns:
        The escaped string.
    """
    return str(value).replace(",", "^,").replace("=", "^=")


def _bool_field(value: bool) -> str:
    """Serialise a boolean to the 'Yes'/'No' string ComicTagger expects."""
    return "Yes" if value else "No"


def build_comictagger_metadata_string(
    metadata: SeriesMetadata,
    volume: Optional[int] = None,
    year: Optional[int] = None,
) -> str:
    """Serialise a metadata dict into the ``-m`` string expected by ComicTagger.

    Volume-specific fields (``volume``, ``year``, ``title``) are injected when
    the corresponding arguments are provided so the same series-level *metadata*
    dict can be reused across multiple volumes.

    Args:
        metadata: Series-level metadata loaded from the JSON file.
        volume:   Volume number parsed from the CBZ filename.
        year:     Publication year parsed from the CBZ filename.

    Returns:
        A comma-delimited ``key=value`` string ready to pass to ``comictagger -m``.
    """
    fields: List[str] = []

    # --- Static series-level fields ---
    fields.append(f"manga={_bool_field(metadata.get('manga', False))}")
    fields.append(f"issue={COMICTAGGER_VOLUME_SENTINEL}")
    fields.append(f"black_and_white={_bool_field(metadata.get('black_and_white', False))}")
    fields.append(f"language={metadata.get('language', '')}")
    fields.append(f"genre={_escape(metadata.get('genre', ''))}")
    fields.append(f"maturity_rating={metadata.get('maturity_rating', '')}")
    fields.append(f"publisher={_escape(metadata.get('publisher', ''))}")
    fields.append(f"imprint={_escape(metadata.get('imprint', ''))}")
    fields.append(f"series={_escape(metadata.get('series', ''))}")
    fields.append(f"series_group={_escape(metadata.get('series_group', ''))}")
    fields.append(f"web_link={_escape(metadata.get('web_link', ''))}")

    # --- Volume-specific fields (omitted when unknown) ---
    if volume is not None:
        fields.append(f"volume={volume}")
        fields.append(f"title=Volume {volume}")
    if year is not None:
        fields.append(f"year={year}")

    # --- Credits ---
    for role, person in metadata.get("credit", {}).items():
        fields.append(f"credit={role}:{person}")

    # --- Characters (multi-value: joined with escaped comma) ---
    characters = metadata.get("characters", [])
    if characters:
        fields.append(f"characters={'^,'.join(characters)}")

    return ",".join(fields)


# ---------------------------------------------------------------------------
# Tagging
# ---------------------------------------------------------------------------

def tag_cbz_files(cbz_files: List[Path], metadata: SeriesMetadata) -> None:
    """Run ComicTagger on every file in *cbz_files*, injecting per-file metadata.

    Volume number and publication year are extracted from each filename so the
    correct values are written even when a single metadata dict covers an entire
    series.

    Args:
        cbz_files: List of .cbz files to tag.
        metadata:  Series-level metadata dict for this collection.
    """
    if not cbz_files:
        logging.info("No .cbz files found to tag.")
        return

    logging.info(f"Tagging {len(cbz_files)} file(s) with ComicTagger.")

    for cbz_file in cbz_files:
        volume = extract_volume_number(cbz_file.name)
        year = extract_publication_year(cbz_file.name)
        metadata_string = build_comictagger_metadata_string(metadata, volume=volume, year=year)

        command = [
            "comictagger",
            "-R",           # recursive (required even for a single file)
            "-s",           # save tags
            "-t", "cr",     # tag type: ComicRack
            "--overwrite",
            "--nosummary",
            "-m", metadata_string,
            str(cbz_file),
        ]

        logging.debug(f"Tagging '{cbz_file.name}' (volume={volume}, year={year}).")
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as exc:
            logging.error(f"ComicTagger failed for '{cbz_file.name}': {exc}")


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def update_file_permissions(directory: Path) -> None:
    """Set standard ownership and permissions on all .cbz files in *directory*.

    This is a no-op on Windows because ``chmod`` / ``chown`` are Unix-only.

    File permissions are set to ``644`` (owner read/write, group/others
    read-only).  Ownership is set to UID 1000 / GID 1001.

    Args:
        directory: Root directory whose .cbz files will be updated.
    """
    if platform.system() == "Windows":
        return

    try:
        subprocess.run(
            ["find", str(directory), "-type", "f", "-name", "*.cbz",
             "-exec", "chmod", FILE_MODE, "{}", "+"],
            check=True,
        )
        subprocess.run(["chown", "-R", FILE_OWNER, str(directory)], check=True)
    except subprocess.CalledProcessError as exc:
        logging.warning(f"Permission update failed for '{directory}': {exc}")


# ---------------------------------------------------------------------------
# Metadata loading
# ---------------------------------------------------------------------------

def load_book_metadata(path: Path) -> Dict[str, SeriesMetadata]:
    """Read the JSON metadata file and return the ``Manga`` section.

    The expected top-level structure is::

        {
            "Manga": {
                "Series Title": { ... },
                ...
            }
        }

    Args:
        path: Path to the JSON metadata file.

    Returns:
        A dict mapping series names to their metadata dicts.

    Raises:
        SystemExit: On any I/O or parse error so the CLI surfaces a clean message.
    """
    if not path.exists():
        logging.error(f"Metadata file '{path}' not found.")
        sys.exit(1)

    try:
        with path.open("r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
    except json.JSONDecodeError as exc:
        logging.error(f"Failed to parse '{path}': {exc}")
        sys.exit(1)

    manga_section = data.get("Manga")
    if not isinstance(manga_section, dict):
        logging.error(f"'{path}' is missing a top-level 'Manga' object.")
        sys.exit(1)

    return manga_section


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_directory(
    directory: Path,
    book_data: Dict[str, SeriesMetadata],
    recent_only: bool = False,
    update_permissions: bool = True,
) -> None:
    """Tag all .cbz files in one series directory.

    Looks up metadata by matching the directory name against the keys in
    *book_data*.  If no matching entry is found the directory is skipped with
    a warning.

    Args:
        directory:          Path to the series directory (e.g. ``./My Manga``).
        book_data:          Full metadata dict loaded from the JSON file.
        recent_only:        When True, only tag recently modified files.
        update_permissions: When True, fix ownership/permissions after tagging.
    """
    series_name = directory.name
    metadata = book_data.get(series_name)

    if metadata is None:
        logging.warning(f"No metadata entry for '{series_name}'. Skipping.")
        return

    cbz_files = get_cbz_files(directory, recent_only=recent_only)
    if not cbz_files:
        logging.info(f"No .cbz files found in '{directory}'.")
        return

    tag_cbz_files(cbz_files, metadata)

    if update_permissions:
        update_file_permissions(directory)

    logging.info(f"Finished tagging '{series_name}'.")


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def prompt_yes_no(question: str) -> bool:
    return input(f"{Fore.RED}{question} (y/n): ").strip().lower().startswith("y")


def prompt_directory_choice(directories: List[Path]) -> Optional[Path]:
    """Interactively ask the user to pick one directory from a numbered list.

    Args:
        directories: The directories to present as choices.

    Returns:
        The selected :class:`Path`, or ``None`` if the user typed ``q``.
    """
    while True:
        print(f"{Fore.YELLOW}Available Directories:")
        for index, directory in enumerate(directories, start=1):
            print(f"  {Fore.RED}{index}. {Fore.GREEN}{directory.name}")

        raw = input(f"{Fore.RED}Choose a directory # or 'q' to quit: ").strip()

        if raw.lower() == "q":
            return None

        if raw.isdigit() and 1 <= int(raw) <= len(directories):
            return directories[int(raw) - 1]

        print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and {len(directories)}.")


def run_interactive_mode(
    subdirs: List[Path],
    book_data: Dict[str, SeriesMetadata],
    update_permissions: bool,
) -> None:
    """Let the user repeatedly pick directories to tag until they quit.

    Args:
        subdirs:            All available subdirectories.
        book_data:          Metadata loaded from the JSON file.
        update_permissions: Forwarded to :func:`process_directory`.
    """
    while True:
        selected = prompt_directory_choice(subdirs)
        if selected is None:
            break

        recent = prompt_yes_no(f"Process only recent files in '{selected.name}'?")
        process_directory(selected, book_data, recent_only=recent, update_permissions=update_permissions)

    logging.info("Finished manual processing.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_argument_parser() -> argparse.ArgumentParser:
    """Create and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Batch tag manga CBZ files using ComicTagger and a JSON metadata file."
    )
    parser.add_argument(
        "-m", "--metadata",
        type=Path,
        default=Path(DEFAULT_METADATA_FILE),
        help=f"Path to the metadata JSON file (default: {DEFAULT_METADATA_FILE}).",
    )
    parser.add_argument(
        "-d", "--directory",
        type=Path,
        default=Path("."),
        help="Root directory containing series subdirectories (default: current directory).",
    )
    parser.add_argument(
        "-r", "--recent",
        action="store_true",
        help=f"Only process .cbz files modified within the last {RECENT_DAYS} days.",
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Automatically process every subdirectory without prompting.",
    )
    parser.add_argument(
        "--no-perms",
        action="store_true",
        help="Skip updating file ownership and permissions after tagging.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) output.",
    )
    return parser


def main() -> None:
    """Parse CLI arguments and run the tagger in batch or interactive mode."""
    parser = build_argument_parser()
    args = parser.parse_args()

    setup_logging(args.verbose)

    book_data = load_book_metadata(args.metadata)

    subdirs = list_subdirectories(args.directory)
    if not subdirs:
        logging.error(f"No subdirectories found in '{args.directory}'.")
        sys.exit(1)

    # --no-perms inverts to a positive "should we update permissions?" flag so
    # it can be passed down without double negatives at every call site.
    should_update_permissions = not args.no_perms

    if args.all:
        for subdir in subdirs:
            process_directory(
                subdir,
                book_data,
                recent_only=args.recent,
                update_permissions=should_update_permissions,
            )
        logging.info("Finished processing all directories.")
    else:
        run_interactive_mode(subdirs, book_data, update_permissions=should_update_permissions)


if __name__ == "__main__":
    main()