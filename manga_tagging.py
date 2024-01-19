# coding=utf8
"""Tired of the default metadata source in comictagger? Do it yourself!"""
import os
import subprocess
import re
import argparse
from colorama import Fore, init

init()

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Interactive Manga Tagging Script")
    parser.add_argument("-d", "--directory", help="Specify the directory to process")
    parser.add_argument("-f", "--file", help="Specify a specific file to process")
    return parser.parse_args()

def list_directories_and_files():
    """List directories and CBZ files in the current working directory.

    Returns:
        Tuple: A tuple containing two lists - dir_list and file_list.
               The 'dir_list' list contains the names of directories in the current directory,
               and the 'file_list' list contains the names of CBZ files.
    """

    dir_list = []
    file_list = []
    for item in os.listdir('.'):
        if os.path.isdir(item):
            dir_list.append(item)
        elif item.endswith(".cbz"):
            file_list.append(item)
    return dir_list, file_list

def choose_directory_or_file(directories, files):
    """Allow the user to choose a directory or CBZ file to work on interactively.

    Args:
        directories (list): A list of directory names.
        files (list): A list of CBZ file names.

    Returns:
        Tuple: A tuple containing two items - selected_directory and selected_file.
               selected_directory (str): The selected directory name, or None if no directory is selected.
               selected_file (str): The selected CBZ file name, or None if no CBZ file is selected.
    """
    while True:
        print(Fore.YELLOW + "Directories:")
        for i, dir_list in enumerate(directories, 1):
            print(Fore.RED + f"{i}." + Fore.GREEN + f" {dir_list}")
        print(Fore.YELLOW + "Files:")
        for i, file_list in enumerate(files, 1):
            print(Fore.RED + f"{i+len(directories)}." + Fore.BLUE + f" {file_list}")
        choice = input(Fore.RESET + "Enter the number of the directory or file you want to work on or type 'exit' to quit: ")
        if choice.lower() == 'exit':
            return None, None
        try:
            choice = int(choice)
            if choice < 1 or choice > len(directories) + len(files):
                raise ValueError
            if choice <= len(directories):
                return directories[choice - 1], None
            else:
                return None, files[choice - len(directories) - 1]
        except ValueError:
            print("Invalid choice. Please enter a valid number.")

def get_directory_path(directory):
    """Get the absolute path of a directory.

    Args:
        directory (str): The name of the directory.

    Returns:
        str: The absolute path of the directory.
    """
    return os.path.abspath(directory)

def check_directory_exists(dir_path):
    """Check if a directory exists.

    Args:
        directory_path (str): The absolute path of the directory.

    Returns:
        bool: True if the directory exists, False otherwise.
    """
    return os.path.exists(dir_path)

def process_cbz_files(dir_path, specific_file=None):
    """Process CBZ files in a directory and update their metadata interactively.

    Args:
        directory_path (str): The absolute path of the directory containing CBZ files.
        specific_file (str): The specific CBZ file to process, or None to process all CBZ files in the directory.
    """
    cbz_files = [file for file in os.listdir(dir_path) if file.endswith(".cbz")]
    cbz_files.sort(key=lambda x: int(extract_volume_number(x)) if extract_volume_number(x) else float('inf'))

    for file in cbz_files:
        if specific_file is not None and file != specific_file:
            continue
        file_path = os.path.join(dir_path, file)
        print(f"Working on file: {file}")
        choice = input("Do you want to skip to the next file? (y/n) ")
        if choice.lower() == 'y':
            continue
        metadata = get_metadata_input()

        if metadata:
            command = get_comictagger_command(metadata, file_path)
            try:
                subprocess.run(command, check=True)
                print("Tagging completed for file:", file)
                print("Updated tags:")
                subprocess.run(["comictagger", "-p", "--type", "CR", file_path], check=True)
            except subprocess.CalledProcessError as e:
                print("Tagging failed for file:", file)
                print("Error:", e)

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
            if not year.isnumeric() or not (1900 <= int(year) <= 2100):
                raise ValueError
            metadata['year'] = year
        month = input("Enter the month: ")
        if month:
            if not month.isnumeric() or not (1 <= int(month) <= 12):
                raise ValueError
            metadata['month'] = month
        day = input("Enter the day: ")
        if day:
            if not day.isnumeric() or not (1 <= int(day) <= 31):
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
    except ValueError:
        print("Invalid input. Please enter a valid value.")
        return None

def clean_string(string):
    """Clean a string by replacing certain characters.

    Args:
        string (str): The string to be cleaned.

    Returns:
        str: The cleaned string.
    """
    return string.replace(',', '^,').replace('=', '^=').strip().replace('  ', ' ').replace('\n', '').replace('...', '…')

def get_comictagger_command(metadata, file_path):
    """Construct the ComicTagger command for updating metadata.

    Args:
        metadata (dict): A dictionary containing metadata fields.
        file_path (str): The path to the CBZ file.

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

    Args:
        title (str): The comic book title.

    Returns:
        str: The extracted volume number, or an empty string if not found.
    """
    # Use a regular expression to match the volume number as a digit
    # The pattern matches the word 'volume', 'vol', or '#', followed by an optional space, followed by one or more digits
    # The digits are captured in a group that can be accessed later
    match = re.search(r"(?:volume|vol\.?|#|v)(\d+)", title, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_arguments()

    if args.directory:
        # If the -d/--directory option is provided, process the specified directory
        directory_path = get_directory_path(args.directory)
        if not check_directory_exists(directory_path):
            print("Directory does not exist.")
        else:
            process_cbz_files(directory_path, specific_file=args.file)
    elif args.file:
        # If the -f/--file option is provided, process the specified file
        process_cbz_files('.', specific_file=args.file)
    else:
        # Otherwise, present the user with a list of directories and files to choose from
        directories, files = list_directories_and_files()
        if len(directories) == 0 and len(files) == 0:
            print("No directories or .cbz files found in the current working directory.")
        else:
            selected_directory, selected_file = choose_directory_or_file(directories, files)
            if selected_directory is None and selected_file is None:
                print("Exiting the program.")
            elif selected_directory is not None:
                directory_path = get_directory_path(selected_directory)
                if not check_directory_exists(directory_path):
                    print("Directory does not exist.")
                else:
                    process_cbz_files(directory_path)
            else:
                process_cbz_files('.', selected_file)
