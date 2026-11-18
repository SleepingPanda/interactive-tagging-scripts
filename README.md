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
dirtag -m comics.json5          # use a different metadata file (e.g. one per library)
dirtag -d /path/to/manga        # specify root directory
dirtag --no-perms               # skip file permission/ownership update
dirtag -v                       # verbose output
```

| Option | Description | Default |
|---|---|---|
| `-m`, `--metadata <PATH>` | Metadata file | `metadata.json5` |
| `-d`, `--directory <PATH>` | Root directory containing the series subdirectories | `.` |
| `-a`, `--all` | Process every subdirectory without prompting | off (interactive) |
| `-r`, `--recent` | Only process `.cbz` files modified in the last 14 days | off |
| `--no-perms` | Skip the chown/chmod step after tagging | off |
| `-v`, `--verbose` | Show DEBUG output | off |

Each immediate subdirectory of the root is treated as one series. `.cbz` files are found recursively inside it (the extension match is case-insensitive) and processed in sorted order. Subdirectories with no matching entry in the metadata file are skipped with a warning.

## Permissions

After tagging a series, `dirtag` changes ownership of everything in that series directory to UID/GID `1000` and sets its `.cbz` files to mode `644`. This does nothing on Windows. To change the owner or mode, edit the constants in `src/permissions.rs`, or pass `--no-perms` to skip the step.

## Metadata

`dirtag` reads series metadata from a [JSON5](https://json5.org) file. Each series is keyed by the **exact directory name** of its folder, under a top-level `Series` key. An optional `Defaults` block supplies values shared by every series.

```json5
{
    // Used by every series that doesn't set its own value.
    Defaults: {
        manga: true,
        black_and_white: true,
        language: "en",
        maturity_rating: "Teen",
    },

    Series: {
        "My Series Name": {
            genre: "Action & Adventure",
            publisher: "Publisher Name",
            imprint: "Imprint Name",
            series: "My Series Name",
            series_group: "My Series Name",
            web_link: "https://example.com/series/my-series",
            characters: ["Character One", "Character Two"],
            credit: {
                // One person in several roles: list the roles in one key.
                "Cover, Inker, Penciller": "Artist Name",
                Writer: "Author Name",
            },
        },

        "A Mature Series": {
            maturity_rating: "M", // overrides the default
            // ...
        },
    },
}
```

Pass it with `-m my_metadata_filename.json5`, or just name it `metadata.json5` and dirtag will find it automatically.

### Fields

| Field | Meaning |
|---|---|
| `manga` | `true` for manga, `false` for western comics |
| `black_and_white` | `true` if the pages are black and white |
| `language`, `genre`, `maturity_rating` | Plain text |
| `publisher`, `imprint` | Plain text |
| `series`, `series_group` | Series name, and a name shared by related series |
| `web_link` | URL for the series |
| `characters` | List of character names |
| `credit` | Role to person, e.g. `Writer: "Jane Doe"` (see below) |

### Defaults

For each field, `dirtag` uses the first value it finds: the series' own entry, then `Defaults`, then empty (`false` for the yes/no fields).

- Setting a field to `""` or `false` in a series is a deliberate value and **does** override a default.
- `characters` is replaced as a whole, never merged.
- `credit` is merged role by role, so a series can override a single role and keep the rest.
- `Defaults` accepts the same fields as a series, and you can leave it out entirely.

### Credit roles

A `credit` key can list several roles separated by commas. They all get the same person:

```json5
credit: { "Cover, Inker, Penciller, Writer": "Hitoshi Iwaaki" }
// is the same as listing each role on its own line
```

Any role names work, so western credits such as `Colorist` and `Letterer` are fine. An empty role name (for example, a stray comma) is an error.

**Credits replace what the file already has.** On its own, ComicTagger *adds* credits to the ones already in the file, which would leave `Old Writer, New Writer`. So for each role you list, `dirtag` first removes that role's existing credits and then writes yours. Roles you don't list are left as they are. To remove a role, list it with an empty person, e.g. `Colorist: ""`.

This relies on ComicTagger 1.5.x behavior and was tested with 1.5.5.

### Using one file per library

A single file holds one set of `Defaults`, so for a mixed collection keep one file per library and pick it with `-m` and `-d`:

```
dirtag -m manga.json5  -d /library/manga  -a
dirtag -m comics.json5 -d /library/comics -a
```

with `manga: true` in the first file's `Defaults` and `manga: false` in the second.

### File format notes

- Plain JSON is valid JSON5, so an existing JSON file works as-is. `Manga` is still accepted as the name of the top-level key (instead of `Series`), so older files load unchanged.
- An unrecognized top-level key (for example a misspelled `Defalts`) is an error, so shared values can't be dropped silently. Unrecognized fields inside a series are ignored.
- A field with the wrong type, such as `manga: "yes"`, will be considered as an error.

### Volumes and filenames

Every file is tagged as a **volume**: the volume number and publication year are taken from the filename, and an issue number is set that lets Kavita treat the file as a single volume instead of a chapter. Issue-based numbering is not supported. Supported filename patterns:

- Volume: `v1`, `v01`, `Vol.2`, `Vol 03`
- Year: `(2023)`

A file with no recognizable volume or year is still tagged, with a warning, and without that field.

## Project layout

| File | Purpose |
|---|---|
| `src/main.rs` | Command-line options and top-level flow |
| `src/metadata.rs` | Metadata file loading (including `Defaults`) and the ComicTagger metadata string |
| `src/filename.rs` | Volume and year extraction from filenames |
| `src/library.rs` | Finding series directories and `.cbz` files |
| `src/permissions.rs` | Ownership/permission fix-up after tagging (Unix only) |
| `src/tagger.rs` | Running ComicTagger on a series |
| `src/interactive.rs` | Interactive menu |
| `src/logger.rs` | Colored log output |

Run the unit tests with `cargo test`.

## License

GPLv3. See [LICENSE](LICENSE).