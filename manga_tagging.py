import os
import subprocess
import re
from colorama import Fore, Style

def list_directories_and_files():
    directories = []
    files = []
    for item in os.listdir('.'):
        if os.path.isdir(item):
            directories.append(item)
        elif item.endswith(".cbz"):
            files.append(item)
    return directories, files

def choose_directory_or_file(directories, files):
    while True:
        print(Fore.YELLOW + "Directories:")
        for i, directory in enumerate(directories, 1):
            print(Fore.RED + f"{i}." + Fore.GREEN + f" {directory}")
        print(Fore.YELLOW + "Files:")
        for i, file in enumerate(files, 1):
             print(Fore.RED + f"{i+len(directories)}." + Fore.BLUE + f" {file}")
        choice = input(Fore.RESET + "Enter the number of the directory or file you want to work on or type 'exit' to quit: ")
        if choice.lower() == 'exit':
            return None, None
        elif not choice.isdigit() or int(choice) < 1 or int(choice) > len(directories) + len(files):
            print("Invalid choice. Please enter a valid number.")
        else:
            choice = int(choice)
            if choice <= len(directories):
                return directories[choice - 1], None
            else:
                return None, files[choice - len(directories) - 1]

def get_directory_path(directory):
    return os.path.abspath(directory)

def check_directory_exists(directory_path):
    return os.path.exists(directory_path)

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

def extract_volume_number(title):
    match = re.search(r"\d{1,3}$", title)
    if match:
        return match.group()
    else:
        return ""

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
