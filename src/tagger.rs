//! Running ComicTagger on the files of a series.

use std::path::Path;
use std::process::Command;

use anyhow::{anyhow, Result};
use log::{debug, error, info, warn};

use crate::filename::{parse_volume, parse_year};
use crate::library::{display_name, find_cbz};
use crate::metadata::{build_metadata_string, Catalog, Series};
use crate::permissions::fix_permissions;

/// Name of the external program that does the actual tagging. It must be on the `PATH`.
const COMICTAGGER: &str = "comictagger";

/// Settings that apply to every series processed in one run.
#[derive(Clone, Copy)]
pub struct TagOptions {
    /// Only tag files modified within the last [`crate::library::RECENT_DAYS`] days.
    pub recent_only: bool,
    /// Hand the series folder back to the configured owner after tagging
    /// (see the `permissions` module).
    pub fix_permissions: bool,
}

/// Checks that ComicTagger can be found, so we can fail early with a clear message instead
/// of failing separately for every file.
pub fn ensure_comictagger_installed() -> Result<()> {
    which::which(COMICTAGGER)
        .map(|_| ())
        .map_err(|_| anyhow!("'{COMICTAGGER}' was not found on PATH."))
}

/// Prepares (but does not run) the ComicTagger command for one file.
///
/// `metadata` is the `key=value,...` string from [`build_metadata_string`]. The arguments
/// are passed to the program one by one rather than through a shell, so spaces and special
/// characters in file names or metadata need no quoting.
fn comictagger_command(file: &Path, metadata: &str) -> Command {
    let mut command = Command::new(COMICTAGGER);
    command
        .args([
            "-R", // required even when tagging a single file
            "-s", // save the tags into the archive
            "-t",
            "cr",          // tag format: ComicRack (ComicInfo.xml)
            "--overwrite", // replace tags the file already has
            "--nosummary", // don't print ComicTagger's summary
            "-m",
        ])
        .arg(metadata)
        .arg(file);
    command
}

/// Tags one `.cbz` file. Failures are logged and do not stop the run.
fn tag_file(file: &Path, series: &Series) {
    let file_name = display_name(file);
    // The volume number and year are not stored in the metadata file; every file in a
    // series has its own, so they are read from the file name.
    let volume = parse_volume(&file_name);
    let year = parse_year(&file_name);
    debug!("Tagging '{file_name}' (volume={volume:?}, year={year:?}).");

    let metadata = build_metadata_string(series, volume, year);
    // `status()` runs the command, waits for it, and lets its output show in the terminal.
    // The outer `Err` means the program could not be started at all; otherwise the exit
    // status says whether ComicTagger itself succeeded.
    match comictagger_command(file, &metadata).status() {
        Ok(status) if status.success() => {}
        Ok(status) => error!("ComicTagger failed for '{file_name}': {status}"),
        Err(error) => error!("Could not run ComicTagger for '{file_name}': {error}"),
    }
}

/// Tags every `.cbz` file in one series directory.
///
/// The series is identified by the directory's name, which must match a key in `catalog`;
/// directories without an entry are skipped with a warning.
pub fn process_series(directory: &Path, catalog: &Catalog, options: TagOptions) {
    let series_name = display_name(directory);
    let Some(series) = catalog.get(&series_name) else {
        warn!("No metadata entry for '{series_name}'. Skipping.");
        return;
    };

    let files = find_cbz(directory, options.recent_only);
    if files.is_empty() {
        info!("No .cbz files found in '{}'.", directory.display());
        return;
    }

    for file in &files {
        tag_file(file, series);
    }
    if options.fix_permissions {
        fix_permissions(directory);
    }
    info!("Finished '{series_name}' ({} file(s)).", files.len());
}