# dirtag

A command-line tool for batch-tagging metadata into CBZ (Comic Book ZIP) files using [ComicTagger](https://github.com/comictagger/comictagger).

`dirtag` tags entire series directories using a JSON5 metadata file. It supports both interactive and fully automatic modes.

## Requirements

- [ComicTagger](https://github.com/comictagger/comictagger) installed and on your `PATH`
- Rust 1.85 or newer, to build from source ([rustup.rs](https://rustup.rs))

## Building

```
cargo build --release
```

The binary is written to `target/release/dirtag`. Copy it anywhere on your `PATH`, or run it in place.

## Usage

```
dirtag                          # interactive mode: pick directories from a list
dirtag -a                       # tag all subdirectories automatically
dirtag -a -r                    # tag only recently modified files (last 14 days)
dirtag -m my_metadata.json5     # use a custom metadata file
dirtag -d /path/to/manga        # specify root directory
dirtag --no-perms               # skip file permission/ownership update
dirtag -v                       # verbose output
```

| Option | Description | Default |
|---|---|---|
| `-m`, `--metadata <PATH>` | Metadata file | `manga.json5` |
| `-d`, `--directory <PATH>` | Root directory containing the series subdirectories | `.` |
| `-a`, `--all` | Process every subdirectory without prompting | off (interactive) |
| `-r`, `--recent` | Only process `.cbz` files modified in the last 14 days | off |
| `--no-perms` | Skip the chown/chmod step after tagging | off |
| `-v`, `--verbose` | Show DEBUG output | off |

Each immediate subdirectory of the root is treated as one series. `.cbz` files are found recursively inside it (the extension match is case-insensitive) and processed in sorted order. Subdirectories with no matching entry in the metadata file are skipped with a warning.

### Permissions

After tagging a series, `dirtag` changes ownership of everything in that series directory to UID/GID `1000` and sets its `.cbz` files to mode `644`. This does nothing on Windows. To change the owner or mode, edit the constants at the top of `src/library.rs`, or pass `--no-perms` to skip the step.

## Metadata file (`manga.json5`)

`dirtag` reads series metadata from a [JSON5](https://json5.org) file. The top-level key must be `Manga`, with each entry keyed by the **exact directory name** of the series.

```json5
{
    // Comments, trailing commas, and single-quoted strings are all allowed.
    Manga: {
        "My Series Name": {
            manga: true,
            black_and_white: true,
            language: "en",
            genre: "Action & Adventure",
            maturity_rating: "Teen",
            publisher: "Publisher Name",
            imprint: "Imprint Name",
            series: "My Series Name",
            series_group: "My Series Name",
            web_link: "https://example.com/series/my-series",
            characters: ["Character One", "Character Two"],
            credit: {
                Writer: "Author Name",
                Penciller: "Artist Name",
                Inker: "Artist Name",
                Cover: "Artist Name",
            },
        },
    },
}
```

Plain JSON is valid JSON5, so an existing `manga.json` works as-is. Pass it with `-m manga.json`, or rename it to `manga.json5` to use the default.

Missing fields are left empty (or `false` for `manga` and `black_and_white`), and unrecognized fields are ignored. A field with the wrong type, such as `manga: "yes"`, is an error.

Volume numbers and publication years are extracted automatically from filenames. Supported patterns:

- Volume: `v1`, `v01`, `Vol.2`, `Vol 03`
- Year: `(2023)`

A file with no recognizable volume or year is still tagged, with a warning, and without that field.

## Project layout

| File | Purpose |
|---|---|
| `src/main.rs` | Command-line options and top-level flow |
| `src/metadata.rs` | Metadata file loading and the ComicTagger metadata string |
| `src/filename.rs` | Volume and year extraction from filenames |
| `src/library.rs` | Finding series directories and `.cbz` files; permissions |
| `src/tagger.rs` | Running ComicTagger on a series |
| `src/interactive.rs` | Interactive menu |
| `src/logger.rs` | Colored log output |

Run the unit tests with `cargo test`.

## License

GPLv3. See [LICENSE](LICENSE).