import argparse
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from colorama import Fore, init

init()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAR_REPLACEMENT_MAPPING = {
    ",": "^,",
    "\n": " ",
    "=": "^=",
    "’": "'",
}

VALIDATION_RANGES = {"year": (1900, 2100), "month": (1, 12), "day": (1, 31)}


def list_dirs_and_files(directory: str = ".") -> Tuple[List[str], List[str]]:
    return (
        sorted([item.name for item in Path(directory).iterdir()
                if item.is_dir()]),
        sorted([str(item) for item in Path(directory).glob("*.cbz")
                if item.is_file()])
    )


def choose_dir_or_file(
    directories: List[str], files: List[str]
) -> Optional[Tuple[Optional[str], Optional[str]]]:
    choices = directories + files
    if not choices:
        return None, None
    print(f"{Fore.YELLOW}Directories:")
    for i, directory in enumerate(directories, 1):
        print(f"{Fore.RED}{i}. {Fore.GREEN}{directory}")
    print(f"{Fore.YELLOW}Files:")
    for i, file in enumerate(files, len(directories) + 1):
        print(f"{Fore.RED}{i}. {Fore.BLUE}{file}")
    choice = input(
        f"{Fore.RED}Enter the number of the directory or file "
        f"you want to work on, or type 'exit' to quit: "
    )
    if choice.lower() == 'exit':
        return None, None
    try:
        choice_num = int(choice) - 1
        if 0 <= choice_num < len(choices):
            if choice_num < len(directories):
                return directories[choice_num], None
            return None, files[choice_num - len(directories)]
        print(f"{Fore.RED}Invalid choice. Please enter a valid number.")
    except ValueError:
        print(f"{Fore.RED}Invalid input. Please enter a valid number.")
    return choose_dir_or_file(directories, files)


def get_directory_path(directory_path: str) -> str:
    if not Path(directory_path).resolve().is_dir():
        raise NotADirectoryError(
            f"The path '{Path(directory_path).resolve()}' is not a directory."
        )
    return str(Path(directory_path).resolve())


def clean_string(input_string: str) -> str:
    cleaned_string = re.sub(
        r"[,\n=]", lambda x: CHAR_REPLACEMENT_MAPPING[x.group()], input_string
    ).strip()
    return re.sub(r"\s+", " ", cleaned_string).replace("...", "…")


def extract_volume_number(title: str) -> str:
    match = re.search(
        r"v(\d+)|volume (\d+)|vol\.? (\d+)|#(\d+)", title, re.IGNORECASE
    )
    return next(filter(None, match.groups()), "") if match else ""


def get_metadata_input() -> Dict[str, str]:
    metadata = {}
    for field in ["year", "month", "day"]:
        while True:
            input_value = input(f"{Fore.RED}Enter the {field}: ")
            if input_value.isnumeric() and VALIDATION_RANGES[field][0] \
                    <= int(input_value) <= VALIDATION_RANGES[field][1]:
                metadata[field] = input_value
                break
            print(
                f"{Fore.RED}Invalid {field}. Please enter a valid numeric "
                f"value within the specified range."
            )
    for field in ["title", "comments"]:
        input_value = input(f"{Fore.RED}Enter the {field}: ")
        if input_value:
            metadata[field] = clean_string(input_value)
    return metadata


def get_comictagger_command(
    metadata: Dict[str, str], file_path: str
) -> List[str]:
    return [
        "comictagger", "-s", "-t", "cr", "--overwrite", "-m",
        ",".join(f"{key}={value}" for key, value in metadata.items()),
        file_path,
    ]


def process_cbz_files(
    directory: str, specific_file: Optional[str] = None
) -> None:
    cbz_files = sorted(
        Path(directory).glob("*.cbz"),
        key=lambda x: int(
            extract_volume_number(x.name)
        ) if extract_volume_number(x.name) else float("inf")
    )
    for idx, file in enumerate(cbz_files):
        if specific_file and file.name != specific_file:
            continue
        print(
            f"{Fore.RED}Working on file "
            f"{idx + 1}/{len(cbz_files)}: {file.name}"
        )
        if input(
            f"{Fore.RED}Do you want to skip to the next file? (y/n) "
        ).lower() == "y":
            continue
        metadata = get_metadata_input()
        if metadata:
            command = get_comictagger_command(metadata, str(file))
            try:
                subprocess.run(command, check=True)
                print(f"{Fore.RED}Tagging completed for file: {file.name}")
                print_tagged_file_metadata(file)
            except subprocess.CalledProcessError as e:
                logger.error("Error while tagging file: %s", file.name)
                logger.error("Error message: %s", str(e))
        else:
            logger.warning(
                "Skipping file %s due to missing metadata.", file.name
            )
    print(f"{Fore.RED}Job completed.")


def print_tagged_file_metadata(file_path: Path) -> None:
    try:
        print(f"{Fore.RED}Updated tags for file: {file_path.name}")
        subprocess.run([
            "comictagger", "-p", "--type", "CR", str(file_path)
        ], check=True)
        subprocess.run([
            "chmod", "644", str(file_path)], check=True)
        subprocess.run(["chown", "1000:1000", str(file_path)], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(
            "Error while printing updated metadata "
            "for file: %s", file_path.name
        )
        logger.error("Error message: %s", str(e))


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tired of the default metadata source in comictagger? \
            Do it yourself!"
    )
    parser.add_argument(
        "-d", "--directory", help="Specify the directory to process"
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        dir_to_process = parse_arguments().directory or "."
        if not Path(dir_to_process).is_dir():
            print(f"{Fore.RED}Directory does not exist.")
            sys.exit(1)
        if parse_arguments().directory:
            process_cbz_files(get_directory_path(dir_to_process))
        else:
            dirs, files = list_dirs_and_files()
            if not (dirs or files):
                print(f"{Fore.RED}No directories or .cbz files found.")
                sys.exit(0)
            result = choose_dir_or_file(dirs, files)
            if result is None:
                print(f"{Fore.RED}Exiting.")
                sys.exit(0)
            selected_directory, selected_file = result
            if selected_directory:
                process_cbz_files(get_directory_path(selected_directory))
            elif selected_file:
                process_cbz_files(".", selected_file)
    except KeyboardInterrupt:
        print(f"{Fore.RED}\nExiting.")
