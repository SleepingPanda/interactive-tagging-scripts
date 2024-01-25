"""Tired of the default metadata source in comictagger? Do it yourself!"""
import os
import re
import sys
import subprocess
import argparse
import logging
from colorama import Fore, init

init()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def list_dirs_and_files(directory='.'):
    """List directories and CBZ files in the specified directory.
    Returns:
        Tuple: A tuple containing two lists - dir_list and file_list.
               The 'dir_list' list contains the names of directories in the specified directory,
               and the 'file_list' list contains the names of CBZ files.
    """
    dir_list = [
        item for item in os.listdir(directory)
        if os.path.isdir(os.path.join(directory, item))
    ]
    file_list = [
        item for item in os.listdir(directory)
        if item.endswith(".cbz")
    ]
    return dir_list, file_list

def choose_dir_or_file(directories, files):
    """Allow the user to interactively choose a directory or CBZ file.
    Returns:
        Tuple: A tuple containing two items - selected_directory and selected_file.
               selected_directory (str): The selected directory name, or None
               if no directory is selected.
               selected_file (str): The selected CBZ file name, or None if no CBZ file is selected.
    """
    while True:
        print(Fore.YELLOW + "Directories:")
        for i, dir_item in enumerate(directories, 1):
            print(Fore.RED + f"{i}." + Fore.GREEN + f" {dir_item}")
        print(Fore.YELLOW + "Files:")
        for i, file_item in enumerate(files, 1):
            print(Fore.RED + f"{i + len(directories)}." + Fore.BLUE + f" {file_item}")
        choice = input(Fore.RESET + "Enter the number of the directory or file you want to work on "
                       "or type 'exit' to quit: ")
        if choice.lower() == 'exit':
            return None, None
        try:
            choice = int(choice)
            if choice < 1 or choice > len(directories) + len(files):
                raise ValueError
            if choice <= len(directories):
                return directories[choice - 1], None
            return None, files[choice - len(directories) - 1]
        except ValueError:
            print("Invalid choice. Please enter a valid number.")

def get_directory_path(directory):
    """Get the absolute path of a directory.
    Returns:
        str: The absolute path of the directory.
    """
    return os.path.abspath(directory)

def check_directory_exists(directory_path):
    """Check if a directory exists.
    Returns:
        bool: True if the directory exists, False otherwise.
    """
    return os.path.exists(directory_path)

def process_cbz_files(directory_to_process, specific_file=None):
    """Process CBZ files in a directory and update their metadata interactively."""
    cbz_files_to_process = [
        file for file in os.listdir(directory_to_process)
        if file.endswith(".cbz")
    ]
    cbz_files_to_process.sort(
        key=lambda x: int(extract_volume_number(x))
        if extract_volume_number(x) else float('inf')
    )
    for file_to_process in cbz_files_to_process:
        if specific_file is not None and file_to_process != specific_file:
            continue
        file_path_to_process = os.path.join(directory_to_process, file_to_process)
        print(f"Working on file: {file_to_process}")
        choice = input("Do you want to skip to the next file? (y/n) ")
        if choice.lower() == 'y':
            continue
        metadata = get_metadata_input()
        if metadata:
            command = get_comictagger_command(metadata, file_path_to_process)
            try:
                subprocess.run(command, check=True)
                print("Tagging completed for file:", file_to_process)
                print("Updated tags:")
                subprocess.run(
                    ["comictagger", "-p", "--type", "CR", file_path_to_process], check=True
                )
            except subprocess.CalledProcessError as e:
                logger.error("Error while tagging file: %s", file_to_process)
                logger.error("Error message: %s", str(e))
        else:
            logger.warning("Skipping file %s due to missing metadata.", file_to_process)
    print("Job completed.")

def get_metadata_input():
    """Prompt the user to input metadata fields for a CBZ file.
    Returns:
        dict: A dictionary containing metadata fields (year, month, day, title, comments).
    """
    metadata = {}
    try:
        year = input("Enter the year: ")
        if year:
            if not year.isnumeric() or not 1900 <= int(year) <= 2100:
                raise ValueError
            metadata['year'] = year
        month = input("Enter the month: ")
        if month:
            if not month.isnumeric() or not 1 <= int(month) <= 12:
                raise ValueError
            metadata['month'] = month
        day = input("Enter the day: ")
        if day:
            if not day.isnumeric() or not 1 <= int(day) <= 31:
                raise ValueError
            metadata['day'] = day
        title = input("Enter the title: ")
        if title:
            metadata['title'] = clean_string(title)
            volume = extract_volume_number(title)
            if volume:
                metadata['volume'] = volume
        comments = input("Enter the comments: ")
        if comments:
            metadata['comments'] = clean_string(comments)
        return metadata
    except ValueError as e:
        raise ValueError("Invalid input. Please enter a valid value.") from e

def clean_string(string):
    """Clean a string by replacing certain characters.
    Returns:
        str: The cleaned string.
    """
    return (
        string.replace(',', '^,')
        .replace('=', '^=')
        .strip()
        .replace('  ', ' ')
        .replace('\n', '')
        .replace('...', '…')
    )

def get_comictagger_command(metadata, file_path):
    """Construct the ComicTagger command for updating metadata.
    Returns:
        list: A list representing the ComicTagger command.
    """
    # The comictagger command has the following format:
    # comictagger -s -t CR --overwrite --metadata field1=value1,field2=value2,... file_path
    # The -s flag means to write tags to the zip comment
    # The -t CR flag means to use the ComicRack tag format
    # The --overwrite flag means to overwrite existing tags
    # The --metadata flag allows to specify the metadata fields and values to update
    # The file_path is the path to the CBZ file
    return [
        "comictagger",
        "-s",
        "-t",
        "CR",
        "--overwrite",
        "--metadata",
        ','.join(f"{key}={value}" for key, value in metadata.items()),
        file_path
    ]

def extract_volume_number(title):
    """Extract the volume number from a title.
    Returns:
        str: The extracted volume number, or an empty string if not found.
    """
    match = re.search(r"(?:volume|vol\.?|#|v)(\d+)", title, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Interactive Manga Tagging Script")
    parser.add_argument("-d", "--directory", help="Specify the directory to process")
    return parser.parse_args()

if __name__ == "__main__":
    try:
        args = parse_arguments()
        if args.directory:
            dir_to_process = get_directory_path(args.directory)
            if not check_directory_exists(dir_to_process):
                print("Directory does not exist.")
            else:
                process_cbz_files(dir_to_process)
        else:
            available_directories, available_files = list_dirs_and_files()
            if len(available_directories) == 0 and len(available_files) == 0:
                print("No directories or .cbz files found in the current working directory.")
            else:
                selected_directory, selected_file = choose_dir_or_file(
                    available_directories, available_files
                )
                if selected_directory is None and selected_file is None:
                    print("Exiting.")
                    sys.exit(0)
                elif selected_directory is not None:
                    dir_to_process = get_directory_path(selected_directory)
                    if not check_directory_exists(dir_to_process):
                        print("Directory does not exist.")
                    else:
                        process_cbz_files(dir_to_process)
                else:
                    process_cbz_files('.', selected_file)
    except KeyboardInterrupt:
        print("\nExiting.")
