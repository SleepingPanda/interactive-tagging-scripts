# Interactive Manga Tagging Script
## Overview

The Interactive Manga Tagging Script is a Python script designed to facilitate the interactive tagging of metadata for CBZ (Comic Book ZIP) files using the ComicTagger tool. It provides a user-friendly interface for processing directories containing CBZ files, allowing users to update metadata fields such as year, month, day, title, and comments interactively.

## Features
- **Directory and File Listing:**

  The script can list directories and CBZ files in the specified directory, providing users with an overview of available options.
- **Interactive Selection:**

  Users can interactively choose a directory or CBZ file, making the tagging process more flexible.
- **Metadata Input:**

  The script prompts users to input metadata fields for each CBZ file, including year, month, day, title, and comments.
- **Metadata Cleaning:**

  Metadata inputs are cleaned to ensure proper formatting and replace certain characters, making them compatible with ComicTagger.
- **Volume Number Extraction:**

  The script can extract volume numbers from titles, providing additional information for the tagging process.
- **Error Handling:**

  The script incorporates error handling for invalid user inputs and provides clear error messages.
- **User-Friendly Interface:**

  The script utilizes the Colorama library for colored console output, enhancing the user interface.

## Usage
1. **Clone the Repository:**
    ```
    git clone https://github.com/SleepingPanda/interactive-manga-tagging-script.git
    cd manual-comictagger-cli
    ```
2. **Install Dependencies:**
    ```
    pip install -u colorama comictagger[all]
    ```
3. **Run the Script:**
  - To process a specific directory:
    ```
    python manga_tagging.py -d /path/to/your/directory
    ```
  - To process the current working directory or select a directory interactively:
    ```
    python manga_tagging.py
    ```
5. **Follow On-Screen Instructions:**
   
   The script will prompt you to choose a directory or CBZ file and interactively input metadata.
7. **Enjoy Interactive Manga/Comic Tagging:**
   
   The script will process CBZ files, allowing you to update metadata interactively using ComicTagger.

## Contribution
Contributions are welcome! Feel free to fork the repository, make improvements, and submit a pull request.

## License
This script is licensed under the GPLv3 License.
