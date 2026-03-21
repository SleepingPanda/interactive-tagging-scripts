# Interactive Tagging Scripts

A Python script for batch-tagging metadata into CBZ (Comic Book ZIP) files using [ComicTagger](https://github.com/comictagger/comictagger).

## Scripts

### `dirtag.py`
Batch-tags entire series directories using a `manga.json` metadata file. Supports both interactive and fully automatic modes.

## Requirements

- Python 3.8+
- ComicTagger installed and on your `PATH`

```
pip install -r requirements.txt
```

## Usage

### `dirtag.py`

```
python dirtag.py                          # interactive mode — pick directories from a list
python dirtag.py -a                       # tag all subdirectories automatically
python dirtag.py -a -r                    # tag only recently modified files (last 14 days)
python dirtag.py -m my_metadata.json      # use a custom metadata file
python dirtag.py -d /path/to/manga        # specify root directory
python dirtag.py --no-perms               # skip file permission/ownership update
python dirtag.py -v                       # verbose output
```

## Metadata file (`manga.json`)

`dirtag.py` reads series metadata from a JSON file. The top-level key must be `"Manga"`, with each entry keyed by the **exact directory name** of the series.

```json
{
    "Manga": {
        "My Series Name": {
            "manga": true,
            "black_and_white": true,
            "language": "en",
            "genre": "Action & Adventure",
            "maturity_rating": "Teen",
            "publisher": "Publisher Name",
            "imprint": "Imprint Name",
            "series": "My Series Name",
            "series_group": "My Series Name",
            "web_link": "https://example.com/series/my-series",
            "characters": ["Character One", "Character Two"],
            "credit": {
                "Writer": "Author Name",
                "Penciller": "Artist Name",
                "Inker": "Artist Name",
                "Cover": "Artist Name"
            }
        }
    }
}
```

Volume numbers and publication years are extracted automatically from filenames. Supported patterns:

- Volume: `v1`, `v01`, `Vol.2`, `Vol 03`
- Year: `(2023)`

## License

GPLv3. See [LICENSE](LICENSE).