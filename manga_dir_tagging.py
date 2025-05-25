import json
import os
import platform
import subprocess
import sys
import time

from colorama import Fore, init

init(autoreset=True)

RECENT_DAYS = 7
DEFAULT_METADATA_FILE = "manga.json"


def list_dirs(directory="."):
    """Return a sorted list of subdirectories in the specified directory."""
    try:
        return sorted(
            d for d in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, d))
        )
    except FileNotFoundError:
        print(f"{Fore.RED}Directory '{directory}' not found.")
        return []


def choose_dir(directories):
    """Prompt the user to choose a directory from a list."""
    while True:
        print(f"{Fore.YELLOW}Available Directories:")
        for i, d in enumerate(directories, 1):
            print(f"{Fore.RED}{i}. {Fore.GREEN}{d}")
        choice = input(f"{Fore.RED}Choose a directory # or type 'exit' to quit: ")
        if choice.lower() == "exit":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(directories):
            return directories[int(choice) - 1]
        print(f"{Fore.RED}Invalid choice. Please enter a number from the list.")


def get_cbz_files(directory, recent_only=False, days=RECENT_DAYS):
    """Get .cbz files in a directory, optionally filtering by modification time."""
    files = []
    threshold = time.time() - days * 86400 if recent_only else 0
    for root, _, filenames in os.walk(directory):
        for name in filenames:
            if name.endswith(".cbz"):
                full_path = os.path.join(root, name)
                if os.path.getmtime(full_path) >= threshold:
                    files.append(full_path)
    return files


def format_metadata(metadata):
    """Convert a metadata dict to a ComicTagger command metadata string."""
    credit = metadata.get("credit", {})
    characters = metadata.get("characters", [])

    credit_str = ", ".join(f"credit={role}:{name}" for role, name in credit.items())
    characters_str = "^,".join(characters)

    return (
        f"manga={metadata.get('manga', '')},"
        f"black_and_white={metadata.get('black_and_white', '')},"
        f"language={metadata.get('language', '')},"
        f"genre={metadata.get('genre', '')},"
        f"maturity_rating={metadata.get('maturity_rating', '')},"
        f"publisher={metadata.get('publisher', '')},"
        f"imprint={metadata.get('imprint', '')},"
        f"series={metadata.get('series', '')},"
        f"series_group={metadata.get('series_group', '')},"
        f"web_link={metadata.get('web_link', '')},"
        f"{credit_str},characters={characters_str}"
    )


def update_permissions(directory):
    """Update file permissions and ownership for CBZ files (Unix only)."""
    if platform.system() == "Windows":
        return

    try:
        subprocess.run(
            ["find", directory, "-type", "f", "-name", "*.cbz", "-exec", "chmod", "644", "{}", "+"],
            check=True
        )
        subprocess.run(["chown", "-R", "1000:1001", directory], check=True)
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Permission update failed: {e}")


def process_dir(directory, book_data, recent_only=False):
    """Tag files in the directory using comictagger."""
    book_name = os.path.basename(directory)
    metadata = book_data.get(book_name)

    if not metadata:
        print(f"{Fore.RED}No metadata found for '{book_name}' in manga.json.")
        return

    cbz_files = get_cbz_files(directory, recent_only=recent_only)
    if not cbz_files:
        print(f"{Fore.YELLOW}No .cbz files to process in {directory}.")
        return

    command = [
        "comictagger", "-R", "-s", "-t", "cr", "--overwrite",
        "-m", format_metadata(metadata),
    ] + cbz_files

    print(f"{Fore.YELLOW}Tagging: {book_name}")
    print(f"{Fore.CYAN}{' '.join(command)}")

    try:
        subprocess.run(command, check=True)
        for path in cbz_files:
            update_permissions(path)
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Tagging failed: {e}")


def load_metadata(path):
    """Load metadata from the given JSON file."""
    if not os.path.exists(path):
        print(f"{Fore.RED}Metadata file '{path}' not found.")
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("Manga", {})
    except (json.JSONDecodeError, KeyError) as e:
        print(f"{Fore.RED}Error loading metadata: {e}")
        sys.exit(1)


def main():
    metadata_path = input(f"{Fore.RED}Path to manga.json (enter for default): ").strip() or DEFAULT_METADATA_FILE
    book_data = load_metadata(metadata_path)

    base_dir = input(f"{Fore.RED}Directory to process (enter for current): ").strip() or "."
    if not os.path.exists(base_dir):
        print(f"{Fore.RED}The directory '{base_dir}' does not exist.")
        return

    subdirs = list_dirs(base_dir)
    if not subdirs:
        print(f"{Fore.RED}No subdirectories found in '{base_dir}'.")
        return

    if input(f"{Fore.RED}Process all subdirectories? (y/n): ").lower().startswith("y"):
        for subdir in subdirs:
            process_dir(os.path.join(base_dir, subdir), book_data)
        print(f"{Fore.GREEN}Finished processing all directories.")
    else:
        while True:
            selected = choose_dir(subdirs)
            if selected is None:
                break
            recent_only = input(f"{Fore.RED}Process only recent files in '{selected}'? (y/n): ").strip().lower().startswith("y")
            process_dir(os.path.join(base_dir, selected), book_data, recent_only=recent_only)

        print(f"{Fore.GREEN}Finished manual processing.")


if __name__ == "__main__":
    main()
