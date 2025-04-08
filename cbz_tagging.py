import argparse
import logging
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from colorama import Fore, init

init()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAR_MAP = {
    ",": "^,",
    "\n": " ",
    "=": "^=",
    "’": "'",
}

VALID_RANGE = {"year": (1900, 2100), "month": (1, 12), "day": (1, 31)}


def list_dirs_and_files(directory: str = ".") -> Tuple[List[str], List[str]]:
    dir_path = Path(directory)
    dir_list = sorted([item.name for item in dir_path.iterdir() if item.is_dir()])
    file_list = sorted([str(item) for item in dir_path.glob("*.cbz")])
    return dir_list, file_list


def display_options(options: List[str], start_index: int, color: str) -> None:
    for i, option in enumerate(options, start_index):
        print(f"{Fore.RED}{i}. {color}{option}")


def choose_dir_or_file(
    directories: List[str], files: List[str]
) -> Tuple[Optional[str], Optional[str]]:
    while True:
        print(f"{Fore.YELLOW}Directories:")
        display_options(directories, 1, Fore.GREEN)
        print(f"{Fore.YELLOW}Files:")
        display_options(files, len(directories) + 1, Fore.BLUE)
        choice = input(
            f"{Fore.RED}Enter the number of "
            f"the directory or file you want to "
            f"work on, or type 'exit' to quit: "
        )

        if choice.lower() == "exit":
            return None, None
        if choice.isdigit():
            choice_num = int(choice)
            if 1 <= choice_num <= len(directories) + len(files):
                return (
                    (directories[choice_num - 1], None)
                    if choice_num <= len(directories)
                    else (None, files[choice_num - len(directories) - 1])
                )
        print(f"{Fore.RED}Invalid choice. Please enter a valid number.")


def get_dir_path(dir_path: str) -> str:
    abs_path = Path(dir_path).resolve(strict=True)
    if not abs_path.is_dir():
        raise NotADirectoryError(f"The path '{abs_path}' is not a directory.")
    return str(abs_path)


def clean_string(input_string: str) -> str:
    cleaned = re.sub(r"[,\n=]", lambda x: CHAR_MAP[x.group()], input_string)
    return re.sub(r"\s+", " ", cleaned.strip()).replace("...", "…")


def extract_volume_number(title: str) -> str:
    match = re.search(r"v(\d+)|volume (\d+)|vol\.? (\d+)|#(\d+)", title, re.IGNORECASE)
    return match.group(1) if match else ""


def get_valid_input(field: str) -> str:
    while True:
        value = input(f"{Fore.RED}Enter the {field}: ")
        if value.isnumeric():
            if VALID_RANGE[field][0] <= int(value) <= VALID_RANGE[field][1]:
                return value
        print(
            f"{Fore.RED}Invalid {field}. Please enter a valid "
            f"numeric value within the specified range."
        )


def get_metadata_input() -> Dict[str, str]:
    metadata = {field: get_valid_input(field) for field in ["year", "month", "day"]}
    for field in ["title", "comments"]:
        value = input(f"{Fore.RED}Enter the {field}: ")
        if value:
            metadata[field] = clean_string(value)
    return metadata


def get_comictagger_command(metadata: Dict[str, str], file_path: str) -> List[str]:
    return [
        "comictagger",
        "-s",
        "-t",
        "cr",
        "--overwrite",
        "-m",
        ",".join(f"{k}={v}" for k, v in metadata.items()),
        file_path,
    ]


def print_tagged_file_metadata(file_path: Path) -> None:
    try:
        print(f"{Fore.RED}Updated tags for file:", file_path.name)
        subprocess.run(
            ["comictagger", "-p", "--type", "CR", str(file_path)], check=True
        )
        if platform.system() != "Windows":
            subprocess.run(["chmod", "644", str(file_path)], check=True)
            subprocess.run(["chown", "1000:1000", str(file_path)], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(
            "Error while printing updated metadata for file: %s", file_path.name
        )
        logger.error("Error message: %s", str(e))


def process_cbz_files(dir_to_process: str, specific_file: Optional[str] = None) -> None:
    directory = Path(dir_to_process)
    if not directory.is_dir():
        logger.error(f"Directory does not exist: {dir_to_process}")
        return
    cbz_files = sorted(
        [file for file in directory.glob("*.cbz") if file.is_file()],
        key=lambda x: (
            int(extract_volume_number(x.name))
            if extract_volume_number(x.name)
            else float("inf")
        ),
    )
    for idx, file in enumerate(cbz_files, start=1):
        if specific_file and file.name != specific_file:
            continue
        print(
            f"{Fore.RED}Working on file {idx}/{
                len(cbz_files)
            }: {file.name}"
        )
        if (
            input(f"{Fore.RED}Do you want to skip to the next file? (y/n) ").lower()
            == "y"
        ):
            continue
        metadata = get_metadata_input()
        command = get_comictagger_command(metadata, str(file.resolve()))
        try:
            subprocess.run(command, check=True)
            print(f"{Fore.RED}Tagging completed for file: {file.name}")
            print_tagged_file_metadata(file.resolve())
        except subprocess.CalledProcessError as e:
            logger.error(f"Error while tagging file: {file.name}")
            logger.error(f"Error message: {str(e)}")
    print(f"{Fore.RED}Job completed.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tired of the default metadata source in "
        "comictagger? Do it yourself!"
    )
    parser.add_argument("-d", "--directory", help="Specify the directory to process.")
    args = parser.parse_args()
    if args.directory and not os.path.exists(args.directory):
        parser.error(
            f"{Fore.RED}The specified directory" f" '{args.directory}'does not exist."
        )
    return args


def process_dir(directory: str) -> None:
    path = get_dir_path(directory)
    process_cbz_files(path)


def handle_interactive_selection() -> None:
    available_dirs, available_files = list_dirs_and_files()
    if not (available_dirs or available_files):
        logger.error(
            "No directories or .cbz files found " "in the current working directory."
        )
        sys.exit(0)
    selected_dir, selected_file = choose_dir_or_file(available_dirs, available_files)
    if selected_dir:
        process_dir(selected_dir)
    elif selected_file:
        process_cbz_files(".", selected_file)
    else:
        print(f"{Fore.RED}Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    try:
        args = parse_arguments()
        if args.directory:
            process_dir(args.directory)
        else:
            handle_interactive_selection()
    except KeyboardInterrupt:
        print(f"{Fore.RED}\nExiting.")
