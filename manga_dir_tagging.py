import json
import os
import platform
import subprocess
import sys
import time

from colorama import Fore, init

init(autoreset=True)


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


def get_recent_cbz_files(directory, days=7):
    """Return list of .cbz files modified in the last `days` days."""
    threshold = time.time() - (days * 86400)
    recent_files = []
    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith(".cbz"):
                full_path = os.path.join(root, f)
                if os.path.getmtime(full_path) >= threshold:
                    recent_files.append(full_path)
    return recent_files


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
    """Tag CBZ files in a directory using metadata from book_data."""
    book_name = os.path.basename(directory)
    metadata = book_data.get(book_name)

    if not metadata:
        print(f"{Fore.RED}No metadata found for '{book_name}' in manga.json.")
        return

    if recent_only:
        cbz_files = get_recent_cbz_files(directory)
        if not cbz_files:
            print(f"{Fore.YELLOW}No recent .cbz files found in {directory}. Skipping.")
            return
    else:
        # Pass the directory so comictagger will find all CBZ files inside
        cbz_files = [directory]

    print(f"{Fore.YELLOW}Updating metadata for: {book_name}")
    tag_command = [
        "comictagger", "-R", "-s", "-t", "cr", "--overwrite",
        "-m", format_metadata(metadata),
    ] + cbz_files

    print(f"{Fore.CYAN}Command: {' '.join(tag_command)}")

    try:
        subprocess.run(tag_command, check=True)
        for path in cbz_files:
            update_permissions(path)
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Failed to tag: {e}")


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
    json_path = input(f"{Fore.RED}Path to manga.json (press enter for 'manga.json'): ").strip() or "manga.json"
    book_data = load_metadata(json_path)

    base_dir = input(f"{Fore.RED}Directory to process (press enter for current): ").strip() or "."
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
        while subdirs:
            selected = choose_dir(subdirs)
            if selected is None:
                break
            recent_only = input(f"{Fore.RED}Process only recent files in '{selected}'? (y/n): ").strip().lower().startswith("y")
            process_dir(os.path.join(base_dir, selected), book_data, recent_only=recent_only)

        print(f"{Fore.GREEN}No more directories left to process.")


if __name__ == "__main__":
    main()
