"""
Tired of the default metadata source in comictagger? Do it yourself!
"""

import argparse
import logging
import os
import re
import subprocess
import sys

from colorama import Fore, init
from pathlib import Path
from typing import List, Tuple, Optional, Dict

init()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def list_dirs_and_files(directory: str = ".") -> Tuple[List[str], List[str]]:
    """
    List directories and CBZ files in the specified directory.
    Args:
        directory (str, optional): The directory path to scan. Defaults to '.'.
    Returns:
        Tuple: A tuple containing two lists - dir_list and file_list.
        The 'dir_list' list contains the names of
        directories in the specified directory, and
        the 'file_list' list contains the names of individual CBZ files.
    Example:
        Given directory structure:
        /my_directory
            ├── subdirectory1/
            ├── subdirectory2/
            ├── file1.cbz
            ├── file2.cbz
            ├── other_file.txt
        Usage:
        >>> list_dirs_and_files('/my_directory')
        (['subdirectory1', 'subdirectory2'],
        ['/my_directory/file1.cbz', '/my_directory/file2.cbz'])
    """
    directory_path = Path(directory)
    dir_list = [item.name for item in directory_path.iterdir() if item.is_dir()]
    file_list = [str(item) for item in directory_path.glob("*.cbz") if item.is_file()]
    return dir_list, file_list


def choose_dir_or_file(directories: List[str], files: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Allow the user to interactively choose a directory or CBZ file.
    Returns:
        Tuple: A tuple containing two items -
        selected_cbz_directory and selected_cbz_file.
        selected_cbz_directory (str): The selected directory name, or None
        if no directory is selected.
        selected_cbz_file (str): The selected CBZ file
        name, or None if no CBZ file is selected.
    """
    while True:
        print(f"{Fore.YELLOW}Directories:")
        for i, directory in enumerate(directories, 1):
            print(f"{Fore.RED}{i}. {Fore.GREEN}{directory}")
        print(f"{Fore.YELLOW}Files:")
        for i, file in enumerate(files, 1):
            print(f"{Fore.RED}{i + len(directories)}. {Fore.BLUE}{file}")
        choice = input(
            f"{Fore.RED}Enter the number of the directory "
            f"or file you want to work on, or type 'exit' to quit: "
        )
        if choice.lower() == 'exit':
            return None, None
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(directories) + len(files):
                if choice_num <= len(directories):
                    return directories[choice_num - 1], None
                else:
                    return None, files[choice_num - len(directories) - 1]
            else:
                print(f"{Fore.RED}Invalid choice. Please enter a valid number.")
        except ValueError:
            print(f"{Fore.RED}Invalid input. Please enter a valid number.")


def get_directory_path(directory_path: str) -> str:
    """
    Get the absolute path of a directory.
    Args:
        directory_path (str): The directory path to be
        validated and converted to absolute path.
    Returns:
        str: The absolute path of the directory.
    Raises:
        ValueError: If the input directory path is an empty string.
        TypeError: If the input directory path is not a string.
        FileNotFoundError: If the specified directory does not exist.
        PermissionError: If the user does not have permission to access the directory.
    """
    if not isinstance(directory_path, str):
        raise TypeError("Input directory must be a string.")
    if not directory_path:
        raise ValueError("Input directory cannot be an empty string.")
    abs_path = Path(directory_path).resolve()
    if not abs_path.exists():
        raise FileNotFoundError(f"The directory '{abs_path}' does not exist.")
    if not abs_path.is_dir():
        raise NotADirectoryError(f"The path '{abs_path}' is not a directory.")
    return str(abs_path)


def check_directory_exists(directory_exists: str) -> bool:
    """
    Check if a directory exists.
    Args:
        directory_exists (str): The directory path to be checked.
    Returns:
        bool: True if the directory exists, False otherwise.
    """
    return os.path.isdir(directory_exists)


CHAR_REPLACEMENT_MAPPING = {
    ",": "^,",
    "\n": " ",
    "=": "^=",
    "’": "'",
}


def clean_string(input_string: str) -> str:
    """
    Clean a string by replacing certain characters.
    This function takes a string as input
    and performs the following operations:
    1. Replaces specified characters according to CHAR_REPLACEMENT_MAPPING.
    2. Strips leading and trailing whitespaces.
    3. Replaces consecutive whitespaces with a single space.
    4. Replaces '...' with the ellipsis character '…'.
    Args:
        input_string (str): The input string to be cleaned.
    Returns:
        str: The cleaned string.
    """
    cleaned_string = re.sub(
        r"[,\n=]", lambda x: CHAR_REPLACEMENT_MAPPING[x.group()], input_string
    ).strip()
    cleaned_string = re.sub(r"\s+", " ", cleaned_string)
    return cleaned_string.replace("...", "…")


def extract_volume_number(title: str) -> str:
    """
    Extract the volume number from a title.
    Args:
        title (str): The title from which to extract the volume number.
    Returns:
        str: The extracted volume number, or an empty string if not found.
    Raises:
        ValueError: If the title is not a string.
    Examples:
        >>> extract_volume_number("Volume 3")
        '3'
        >>> extract_volume_number("Vol. 5")
        '5'
        >>> extract_volume_number("Chapter 7")
        '7'
        >>> extract_volume_number("v09")
        '09'
    Note:
        The function looks for specific patterns
        like 'v,' 'volume,' 'vol,' or '#' followed by digits
        to extract the volume number. It provides flexibility
        for different volume number formats.
    """
    if not isinstance(title, str):
        raise ValueError("Title must be a string.")
    if match := re.search(
        r"v(\d+)|volume (\d+)|vol\.? (\d+)|#(\d+)", title, re.IGNORECASE
    ):
        return next(filter(None, match.groups()), "")
    return ""


VALIDATION_RANGES = {"year": (1900, 2100), "month": (1, 12), "day": (1, 31)}


def get_metadata_input() -> Dict[str, str]:
    """
    Prompt the user to input metadata fields for a CBZ file.
    Returns:
        Dict[str, str]: A dictionary containing metadata
        fields (year, month, day, title, comments).
    """
    metadata = {}
    for field in ["year", "month", "day"]:
        while True:
            input_value = input(f"{Fore.RED}Enter the {field}: ")
            if input_value.isnumeric():
                parsed_value = int(input_value)
                if (
                    VALIDATION_RANGES[field][0] <= parsed_value <= VALIDATION_RANGES[field][1]
                ):
                    metadata[field] = str(parsed_value)
                    break
            print(
                f"{Fore.RED}Invalid {field}. Please enter a valid numeric "
                f"{Fore.RED}value within the specified range."
            )
    metadata_fields = ["title", "comments"]
    for field in metadata_fields:
        input_value = input(f"{Fore.RED}Enter the {field}: ")
        if input_value:
            metadata[field] = clean_string(input_value)
    return metadata


def get_comictagger_command(metadata: Dict[str, str], file_path: str) -> List[str]:
    """
    Construct the ComicTagger command for updating metadata.
    Returns:
        list: A list representing the ComicTagger command.
    """
    # The comictagger command has the following format:
    # comictagger -s -t cr --overwrite -m field1=value1,field2=value2,... file_path
    # The -s flag means to write tags to the zip comment
    # The -t cr flag means to use the ComicRack tag format
    # The --overwrite flag means to overwrite existing tags
    # The -m flag allows specifying the metadata fields and values to update
    # The file_path is the path to the CBZ file
    return [
        "comictagger",
        "-s",
        "-t",
        "cr",
        "--overwrite",
        "-m",
        ",".join(f"{key}={value}" for key, value in metadata.items()),
        file_path,
    ]


def process_cbz_files(directory_to_process: str, specific_file: Optional[str] = None) -> None:
    """
    Process CBZ files in a directory and update their metadata interactively.
    """
    if not Path(directory_to_process).is_dir():
        print(f"Directory does not exist: {directory_to_process}")
        return
    cbz_files_to_process = sorted(
        [file for file in Path(directory_to_process).glob("*.cbz") if file.is_file()],
        key=lambda x: (int(extract_volume_number(x.name)) if extract_volume_number(x.name) else float("inf"))
    )
    for idx, file_to_process in enumerate(cbz_files_to_process):
        if specific_file is not None and file_to_process.name != specific_file:
            continue
        file_path_to_process = file_to_process.resolve()
        print(
            f"{Fore.RED}Working on file "
            f"{Fore.RED}{idx + 1}/{len(cbz_files_to_process)}: {file_to_process.name}"
        )
        choice = input(f"{Fore.RED}Do you want to skip to the next file? (y/n) ")
        if choice.lower() == "y":
            continue
        if metadata := get_metadata_input():
            command = get_comictagger_command(metadata, str(file_path_to_process))
            try:
                subprocess.run(command, check=True)
                print(f"{Fore.RED}Tagging completed for file:", file_to_process.name)
                print_tagged_file_metadata(file_path_to_process)
            except subprocess.CalledProcessError as e:
                logger.error("Error while tagging file: %s", file_to_process.name)
                logger.error("Error message: %s", str(e))
        else:
            logger.warning("Skipping file %s due to missing metadata.", file_to_process.name)
    print(f"{Fore.RED}Job completed.")


def print_tagged_file_metadata(file_path: Path):
    try:
        print(f"{Fore.RED}Updated tags for file:", file_path.name)
        subprocess.run(
            ["comictagger", "-p", "--type", "CR", str(file_path)],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error("Error while printing updated metadata for file: %s", file_path.name)
        logger.error("Error message: %s", str(e))


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Tired of the default metadata source "
        "in comictagger? Do it yourself!"
    )
    parser.add_argument("-d", "--directory", help="Specify the directory to process")
    cbz_args = parser.parse_args()
    directory = cbz_args.directory
    if directory and not os.path.exists(directory):
        parser.error(f"{Fore.RED}The specified directory '{directory}' does not exist.")
    return cbz_args


if __name__ == "__main__":
    try:
        args = parse_arguments()
        if args.directory:
            dir_to_process = get_directory_path(args.directory)
            if not check_directory_exists(dir_to_process):
                print(f"{Fore.RED}Directory does not exist.")
            else:
                process_cbz_files(dir_to_process)
        else:
            available_directories, available_files = list_dirs_and_files()
            if not (available_directories or available_files):
                print(
                    f"{Fore.RED}No directories or .cbz files "
                    f"{Fore.RED}found in the current working directory."
                )
            else:
                selected_directory, selected_file = choose_dir_or_file(
                    available_directories, available_files
                )
                if selected_directory is None and selected_file is None:
                    print(f"{Fore.RED}Exiting.")
                    sys.exit(0)
                elif selected_directory is not None:
                    dir_to_process = get_directory_path(selected_directory)
                    if not check_directory_exists(dir_to_process):
                        print(f"{Fore.RED}Directory does not exist.")
                    else:
                        process_cbz_files(dir_to_process)
                else:
                    process_cbz_files(".", selected_file)
    except KeyboardInterrupt:
        print(f"{Fore.RED}\nExiting.")
