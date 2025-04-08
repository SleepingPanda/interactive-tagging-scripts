import json
import os
import platform
import subprocess

from colorama import Fore, init

init()


def list_dirs(directory="."):
    """List directories in the given directory."""
    return sorted(
        item
        for item in os.listdir(directory)
        if os.path.isdir(os.path.join(directory, item))
    )


def choose_dir(directories):
    """Prompt user to choose a directory from a list."""
    while True:
        print(f"{Fore.YELLOW}Directories:")
        for i, selected_dir in enumerate(directories, 1):
            print(f"{Fore.RED}{i}. {Fore.GREEN}{selected_dir}")
        choice = input(f"{Fore.RED}Enter directory # or 'exit' to quit: ")
        if choice.lower() == "exit":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(directories):
            return directories[int(choice) - 1]
        print(f"{Fore.RED}Invalid input. Please enter a valid #.")


def format_metadata(metadata):
    """Format the metadata for the command."""
    return (
        "manga={manga},black_and_white={black_and_white},"
        "language={language},genre={genre},"
        "maturity_rating={maturity_rating},publisher={publisher},"
        "imprint={imprint},series={series},series_group={series_group},"
        "web_link={web_link},{credit_str},characters={characters}".format(
            manga=metadata.get("manga", ""),
            black_and_white=metadata.get("black_and_white", ""),
            language=metadata.get("language", ""),
            genre=metadata.get("genre", ""),
            maturity_rating=metadata.get("maturity_rating", ""),
            publisher=metadata.get("publisher", ""),
            imprint=metadata.get("imprint", ""),
            series=metadata.get("series", ""),
            series_group=metadata.get("series_group", ""),
            web_link=metadata.get("web_link", ""),
            credit_str=", ".join(
                f"credit={role}:{person}" for role, person in metadata.get("credit", {}).items()
            ),
            characters="^,".join(metadata.get("characters", [])),
        )
    )


def process_dir(dir_path, book_data):
    """Process the directory with the given book data."""
    book_name = os.path.basename(dir_path)
    metadata = book_data.get(book_name)
    if not metadata:
        print(f"{Fore.RED}No metadata found for" f" '{book_name}' in manga.json.")
        return
    command = [
        "comictagger",
        "-R",
        "-s",
        "-t",
        "cr",
        "--overwrite",
        "-m",
        format_metadata(metadata),
        dir_path,
    ]
    print(f"{Fore.RED}Updating metadata for directory: {book_name}")
    print(" ".join(command))
    subprocess.run(command, check=True)
    if platform.system() != "Windows":
        subprocess.run(
            [
                "find",
                dir_path,
                "-type",
                "f",
                "-name",
                "*.cbz",
                "-exec",
                "chmod",
                "644",
                "{}",
                "+",
            ]
        )
        subprocess.run(["chown", "-R", "1000:1000", dir_path])


def write_json_tag():
    """Main function to write JSON tag to the directory."""
    manga_json_path = (
        input(
            f"{Fore.RED}Input path to manga.json "
            "(or press return to use 'manga.json'): "
        )
        or "manga.json"
    )
    with open(manga_json_path, "r", encoding="utf-8") as file:
        book_data = json.load(file)["Manga"]

    dir_path = (
        input(
            f"{Fore.RED}Enter the directory path to process "
            "(leave blank to use the current directory): "
        )
        or "."
    )

    if os.path.exists(dir_path):
        all_dirs = list_dirs(dir_path)
        if not all_dirs:
            print(f"{Fore.RED}No directories found in '{dir_path}'. Exiting.")
            return

        process_all = input(
            f"{Fore.RED}Process all directories in '{dir_path}'? (yes/no): "
        ).strip().lower()

        if process_all in {"yes", "y"}:
            # Automatically process all directories
            for sub_dir in all_dirs:
                sub_dir_path = os.path.join(dir_path, sub_dir)
                print(f"{Fore.YELLOW}Processing directory: {sub_dir_path}")
                process_dir(sub_dir_path, book_data)
            print(f"{Fore.GREEN}Finished processing all directories.")
        else:
            # Allow the user to manually choose directories one at a time
            while True:
                selected_dir = choose_dir(all_dirs)
                if not selected_dir:
                    print(f"{Fore.RED}Exiting.")
                    return
                selected_path = os.path.join(dir_path, selected_dir)
                process_dir(selected_path, book_data)

                # Remove the processed directory from the list
                all_dirs.remove(selected_dir)

                # If no directories remain, exit
                if not all_dirs:
                    print(f"{Fore.GREEN}No more directories left to process.")
                    break
    else:
        print(f"{Fore.RED}The directory '{dir_path}' does not exist.")


if __name__ == "__main__":
    write_json_tag()
