"""tag directories of files"""

import json
import os
import subprocess

from colorama import Fore, init

init()


def list_dirs(directory="."):
    """
    List directories in the specified directory.
    """
    return [
        item
        for item in os.listdir(directory)
        if os.path.isdir(os.path.join(directory, item))
    ]


def choose_dir(directories):
    """
    Allow the user to interactively choose a directory or CBZ file.
    """
    while True:
        print(f"{Fore.YELLOW}Directories:")
        for i, selected_dir in enumerate(directories, 1):
            print(f"{Fore.RED}{i}. {Fore.GREEN}{selected_dir}")
        choice = input(
            f"{Fore.RED}Enter the # of the directory "
            "you want to work on or type 'exit' to quit: "
        )
        if choice.lower() == "exit":
            return None
        if choice.isdigit():
            choice = int(choice)
            if 1 <= choice <= len(directories):
                return directories[choice - 1]
            print(f"{Fore.RED}Invalid choice. Please enter a valid #.")
        else:
            print(f"{Fore.RED}Invalid input. Please enter a valid #.")


def process_dir(dir_path, book_data):
    """
    Process the directory of files and update their metadata.
    """
    book_name = os.path.basename(dir_path)
    if book_name in book_data:
        metadata = book_data[book_name]
        command = ["comictagger", "-R", "-s", "-t", "cr", "--overwrite", "-m"]
        template = "manga={manga},black_and_white={black_and_white},language={language},genre={genre},maturity_rating={maturity_rating},publisher={publisher},imprint={imprint},series={series},series_group={series_group},web_link={web_link},{credit_str},characters={characters}"
        metadata_str = template.format(
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
                [
                    f"credit={credit_key}:{credit_value}"
                    for credit_key, credit_value in metadata.get("credit", {}).items()
                ]
            ),
            characters="^,".join(metadata.get("characters", [])),
        )
        command.append(metadata_str)
        command.append(dir_path)
        print(f"{Fore.RED}Updating metadata for directory: {book_name}")
        print(" ".join(command))
        subprocess.run(command, check=True)
    else:
        print(f"{Fore.RED}No metadata found for '{book_name}' in manga.json.")


def write_json_tag():
    manga_json_path = input(
        f"{Fore.RED}Input path to manga.json (leave blank for default 'manga.json'): "
    )
    if not manga_json_path:
        manga_json_path = "manga.json"
    with open(manga_json_path, "r", encoding="utf-8") as file:
        book_data = json.load(file)["books"]
    dir_path = input(
        f"{Fore.RED}Enter the directory path to process "
        f"{Fore.RED}(leave blank to list directories): "
    )
    if not dir_path:
        dir_path = "."
        dirs = list_dirs(dir_path)
        selected_dir = choose_dir(dirs)
        if selected_dir:
            dir_path = os.path.join(dir_path, selected_dir)
        else:
            print(f"{Fore.RED}Exiting.")
            return
    if os.path.exists(dir_path):
        process_dir(dir_path, book_data)
    else:
        print(f"{Fore.RED}The directory '{dir_path}' does not exist.")


if __name__ == "__main__":
    write_json_tag()
