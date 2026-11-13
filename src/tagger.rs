//! Running ComicTagger on a series.

use std::path::{Path, PathBuf};
use std::process::Command;

use log::{debug, error, info, warn};

use crate::filename::{parse_volume, parse_year};
use crate::library::{dir_name, find_cbz, fix_permissions};
use crate::metadata::{build_metadata_string, Book, Series};

/// Run ComicTagger on each file, deriving volume and year from its name.
fn tag_files(files: &[PathBuf], meta: &Series) {
    for cbz in files {
        let name = dir_name(cbz);
        let volume = parse_volume(&name);
        let year = parse_year(&name);
        debug!("Tagging '{name}' (volume={volume:?}, year={year:?}).");
        let status = Command::new("comictagger")
            .args([
                "-R", // required even for a single file
                "-s", // save tags
                "-t", "cr", // ComicRack tag format
                "--overwrite",
                "--nosummary",
                "-m",
            ])
            .arg(build_metadata_string(meta, volume, year))
            .arg(cbz)
            .status();
        match status {
            Ok(s) if s.success() => {}
            Ok(s) => error!("ComicTagger failed for '{name}': {s}"),
            Err(e) => error!("Could not run ComicTagger for '{name}': {e}"),
        }
    }
}

/// Tag all .cbz files in one series directory, matched by directory name.
pub fn process_series(directory: &Path, book: &Book, recent_only: bool, perms: bool) {
    let name = dir_name(directory);
    let Some(meta) = book.get(&name) else {
        warn!("No metadata entry for '{name}'. Skipping.");
        return;
    };
    let files = find_cbz(directory, recent_only);
    if files.is_empty() {
        info!("No .cbz files found in '{}'.", directory.display());
        return;
    }
    tag_files(&files, meta);
    if perms {
        fix_permissions(directory);
    }
    info!("Finished '{name}' ({} file(s)).", files.len());
}