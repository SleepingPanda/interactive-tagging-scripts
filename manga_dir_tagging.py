#!/usr/bin/env python3
import argparse
import json
import logging
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

from colorama import Fore, init

init(autoreset=True)

RECENT_DAYS = 14
DEFAULT_METADATA_FILE = "manga.json"


def setup_logging(verbose: bool) -> None:
    """Configure logging output."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=f"{Fore.CYAN}[%(levelname)s]{Fore.RESET} %(message)s",
    )


def list_dirs(directory: Path) -> List[Path]:
    """Return a sorted list of subdirectories."""
    if not directory.exists():
        logging.error(f"Directory '{directory}' does not exist.")
        return []
    return sorted([d for d in directory.iterdir() if d.is_dir()])


def choose_dir(directories: List[Path]) -> Optional[Path]:
    """Prompt the user to select a subdirectory interactively."""
    while True:
        print(f"{Fore.YELLOW}Available Directories:")
        for i, d in enumerate(directories, start=1):
            print(f"{Fore.RED}{i}. {Fore.GREEN}{d.name}")
        choice = input(f"{Fore.RED}Choose a directory # or 'q' to quit: ").strip()
        if choice.lower() == "q":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(directories):
            return directories[int(choice) - 1]
        print(f"{Fore.RED}Invalid choice. Please try again.")


def get_cbz_files(directory: Path, recent_only: bool = False, days: int = RECENT_DAYS) -> List[Path]:
    """Return list of .cbz files within a directory."""
    threshold = time.time() - days * 86400 if recent_only else 0
    return [
        f for f in directory.rglob("*.cbz")
        if not recent_only or f.stat().st_mtime >= threshold
    ]


def escape_value(value: Any) -> str:
    """Escape commas and equal signs in metadata values."""
    return str(value).replace(",", "^,").replace("=", "^=")


def extract_volume(filename: str) -> Optional[int]:
    """Extract volume number as an integer from a CBZ filename.

    Matches patterns like 'v01', 'v1', 'Vol.2', 'Vol 03', etc.
    Returns None if no volume number is found.
    """
    match = re.search(r"[Vv](?:ol\.?\s*)?(\d+)", filename)
    if match:
        return int(match.group(1))
    logging.warning(f"Could not extract volume number from '{filename}'.")
    return None


def extract_year(filename: str) -> Optional[int]:
    """Extract a 4-digit year from parentheses in a CBZ filename.

    Matches patterns like '(2023)'.
    Returns None if no year is found.
    """
    match = re.search(r"\((\d{4})\)", filename)
    if match:
        return int(match.group(1))
    logging.warning(f"Could not extract year from '{filename}'.")
    return None


def format_metadata(metadata: Dict[str, Any], volume: Optional[int] = None, year: Optional[int] = None) -> str:
    """Format metadata dictionary into ComicTagger CLI string.

    Args:
        metadata: Series-level metadata dict.
        volume:   Volume number extracted from the CBZ filename. When provided,
                  it is written to the ``volume`` field in the tag.
        year:     Publication year extracted from the CBZ filename. When provided,
                  it is written to the ``year`` field in the tag.
    """
    credit = metadata.get("credit", {})
    characters = metadata.get("characters", [])
    credit_str = ", ".join(f"credit={role}:{name}" for role, name in credit.items())
    characters_str = "^,".join(characters)
    volume_str = f"volume={volume}," if volume is not None else ""
    year_str = f"year={year}," if year is not None else ""
    title_str = f"title=Volume {volume}," if volume is not None else ""
    return (
        f"manga={metadata.get('manga', '')},"
        f"issue=-100000,"
        f"{volume_str}"
        f"{year_str}"
        f"{title_str}"
        f"black_and_white={metadata.get('black_and_white', '')},"
        f"language={metadata.get('language', '')},"
        f"genre={escape_value(metadata.get('genre', ''))},"
        f"maturity_rating={metadata.get('maturity_rating', '')},"
        f"publisher={escape_value(metadata.get('publisher', ''))},"
        f"imprint={escape_value(metadata.get('imprint', ''))},"
        f"series={escape_value(metadata.get('series', ''))},"
        f"series_group={escape_value(metadata.get('series_group', ''))},"
        f"web_link={escape_value(metadata.get('web_link', ''))},"
        f"{credit_str},characters={characters_str}"
    )


def update_permissions(directory: Path) -> None:
    """Update Unix file permissions for CBZ files."""
    if platform.system() == "Windows":
        return
    try:
        subprocess.run(
            [
                "find", directory, "-type", "f", "-name",
                "*.cbz", "-exec", "chmod", "644", "{}", "+"
            ],
            check=True
        )
        subprocess.run(["chown", "-R", "1000:1001", str(directory)], check=True)
    except subprocess.CalledProcessError as e:
        logging.warning(f"Permission update failed for '{directory}': {e}")


def tag_cbz_files(cbz_files: List[Path], metadata: Dict[str, Any]) -> None:
    """Run ComicTagger command for each file, injecting its volume number."""
    if not cbz_files:
        logging.info("No .cbz files found to tag.")
        return
    logging.info(f"Running ComicTagger for {len(cbz_files)} files.")
    for cbz_file in cbz_files:
        volume = extract_volume(cbz_file.name)
        year = extract_year(cbz_file.name)
        command = [
            "comictagger", "-R", "-s", "-t", "cr", "--overwrite",
            "-m", format_metadata(metadata, volume=volume, year=year),
            str(cbz_file),
        ]
        logging.debug(f"Tagging '{cbz_file.name}' (volume={volume}, year={year}).")
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"ComicTagger failed for '{cbz_file.name}': {e}")


def load_metadata(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load metadata from JSON file."""
    if not path.exists():
        logging.error(f"Metadata file '{path}' not found.")
        sys.exit(1)
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f).get("Manga", {})
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Error reading metadata: {e}")
        sys.exit(1)


def process_directory(directory: Path, book_data: Dict[str, Any], recent_only: bool = False) -> None:
    """Process one directory."""
    book_name = directory.name
    metadata = book_data.get(book_name)
    if not metadata:
        logging.warning(f"No metadata for '{book_name}'. Skipping.")
        return
    cbz_files = get_cbz_files(directory, recent_only=recent_only)
    if not cbz_files:
        logging.info(f"No .cbz files found in '{directory}'.")
        return
    tag_cbz_files(cbz_files, metadata)
    update_permissions(directory)
    logging.info(f"Finished tagging '{book_name}'.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch tag manga CBZ files using ComicTagger metadata."
    )
    parser.add_argument("-m", "--metadata", type=Path, default=Path(DEFAULT_METADATA_FILE),
                        help="Path to metadata JSON (default: manga.json)")
    parser.add_argument("-d", "--directory", type=Path, default=Path("."),
                        help="Directory to process (default: current)")
    parser.add_argument("-r", "--recent", action="store_true",
                        help=f"Process only CBZ files modified in the last {RECENT_DAYS} days.")
    parser.add_argument("-a", "--all", action="store_true",
                        help="Process all subdirectories automatically.")
    parser.add_argument("--no-perms", action="store_true",
                        help="Skip updating file ownership/permissions.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output.")
    args = parser.parse_args()
    setup_logging(args.verbose)
    book_data = load_metadata(args.metadata)
    subdirs = list_dirs(args.directory)
    if not subdirs:
        logging.error(f"No subdirectories found in '{args.directory}'.")
        sys.exit(1)
    if args.all:
        for subdir in subdirs:
            process_directory(subdir, book_data, recent_only=args.recent)
        logging.info("Finished processing all directories.")
    else:
        while True:
            selected = choose_dir(subdirs)
            if not selected:
                break
            recent = input(f"{Fore.RED}Process only recent files in '{selected.name}'? (y/n): ").lower().startswith("y")
            process_directory(selected, book_data, recent_only=recent)
        logging.info("Finished manual processing.")


if __name__ == "__main__":
    main()