# Interactive Tagging Scripts
## Overview

Interactive Tagging Scripts are a collection of Python scripts designed to facilitate the interactive tagging of metadata for CBZ (Comic Book ZIP) files using the ComicTagger tool. They provides a user-friendly interface for processing directories containing CBZ files, allowing users to update metadata fields interactively.

## Features
- **Directory and File Listing:**

  The scripts can list directories and CBZ files in a specified directory, providing users with an overview of available options.
- **Interactive Selection:**

  Users can interactively choose directories of files or individual CBZ files to work on, making the tagging process more flexible.
- **Metadata Input:**

  The scripts prompts users to input metadata fields for each CBZ file or use a predefined json file to automatically tag entire directories.
- **Metadata Cleaning:**

  Metadata inputs are cleaned to ensure proper formatting and replaces certain characters, making them compatible with ComicTagger.
- **Volume Number Extraction:**

  The scripts can extract volume numbers from filenames automatically, providing additional information for the tagging process.
- **Error Handling:**

  The scripts incorporates error handling for invalid user inputs and provides clear error messages.
- **User-Friendly Interface:**

  The scripts utilize the Colorama library for colored console output, enhancing the user experience.

## Usage
1. **Clone the Repository:**
    ```
    git clone https://github.com/SleepingPanda/interactive-tagging-scripts.git
    cd interactive-tagging-scripts
    ```
2. **Install Dependencies:**
    ```
    pip install -r requirements.txt
    ```
3. **Run the Scripts:**
  - To process a specific directory:
    ```
    python cbz_tagging.py -d /path/to/your/directory
    ```
  - To process the current working directory or select a directory interactively:
    ```
    python cbz_tagging.py
    ```
  - To automatically tag an entire dir of files:
    ```
    python manga_dir_tagging.py
    ```
5. **Follow On-Screen Instructions:**
   
   The scripts will prompt you to choose from directories or individual CBZ files and interactively input metadata.

## Contribution
Contributions are welcome! Feel free to fork the repository, make improvements, and submit a pull request.

## License
These scripts are licensed under the GPLv3 License.
