//! Looking around the comic library on disk: finding series folders and their `.cbz` files.
//!
//! Expected layout: the root directory contains one folder per series, and each series
//! folder contains `.cbz` files (possibly nested in further subfolders).
//!
//! ```text
//! library/
//! ├── My Series/
//! │   ├── My Series v01 (2020).cbz
//! │   └── My Series v02 (2021).cbz
//! └── Another Series/
//!     └── ...
//! ```

use std::fs;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};

use log::warn;
use walkdir::{DirEntry, WalkDir};

/// How far back "recent" reaches when only recently modified files are wanted.
pub const RECENT_DAYS: u64 = 14;

const SECONDS_PER_DAY: u64 = 24 * 60 * 60;

/// The last component of a path (a file or folder name) as a `String`.
///
/// Names that are not valid UTF-8 are converted lossily, which is fine for logging and for
/// looking a series up by name. Returns an empty string for paths without a final name.
pub fn display_name(path: &Path) -> String {
    path.file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .into_owned()
}

/// The immediate subdirectories of `root` (one per series), sorted by name.
///
/// Entries that cannot be read are skipped.
pub fn subdirectories(root: &Path) -> anyhow::Result<Vec<PathBuf>> {
    use anyhow::Context;

    let mut directories: Vec<PathBuf> = fs::read_dir(root)
        .with_context(|| format!("Cannot read '{}'", root.display()))?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.is_dir())
        .collect();
    directories.sort();
    Ok(directories)
}

/// True for a regular file whose extension is `.cbz`, in any letter case.
///
/// The `is_file()` check (which follows symlinks) excludes folders that happen to be named
/// like `something.cbz`.
pub fn is_cbz_file(path: &Path) -> bool {
    let has_cbz_extension = path
        .extension()
        .is_some_and(|extension| extension.eq_ignore_ascii_case("cbz"));
    has_cbz_extension && path.is_file()
}

/// True if the file was last modified at or after `cutoff`.
/// Files whose modification time cannot be read count as "not modified".
fn modified_since(path: &Path, cutoff: SystemTime) -> bool {
    fs::metadata(path)
        .and_then(|metadata| metadata.modified())
        .is_ok_and(|modified| modified >= cutoff)
}

/// Finds every `.cbz` file below `directory`, sorted so runs are reproducible.
///
/// With `recent_only`, files not modified within the last [`RECENT_DAYS`] days are left out.
pub fn find_cbz(directory: &Path, recent_only: bool) -> Vec<PathBuf> {
    let cutoff = SystemTime::now() - Duration::from_secs(RECENT_DAYS * SECONDS_PER_DAY);

    let mut files: Vec<PathBuf> = WalkDir::new(directory)
        .into_iter()
        // A folder we cannot read is reported and skipped; it should not abort the run.
        .filter_map(|entry| entry.map_err(|error| warn!("{error}")).ok())
        .map(DirEntry::into_path)
        .filter(|path| is_cbz_file(path))
        .filter(|path| !recent_only || modified_since(path, cutoff))
        .collect();
    files.sort();
    files
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;

    /// Creates an empty file (and any missing parent folders) and returns its path.
    fn touch(root: &Path, relative: &str) -> PathBuf {
        let path = root.join(relative);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        File::create(&path).unwrap();
        path
    }

    #[test]
    fn display_name_is_last_component() {
        assert_eq!(
            display_name(Path::new("/a/b/Series v01.cbz")),
            "Series v01.cbz"
        );
        assert_eq!(display_name(Path::new("/")), "");
    }

    #[test]
    fn finds_cbz_recursively_in_sorted_order_ignoring_other_files() {
        let dir = tempfile::tempdir().unwrap();
        let b = touch(dir.path(), "b.cbz");
        let upper = touch(dir.path(), "a.CBZ");
        let nested = touch(dir.path(), "sub/c.cbz");
        touch(dir.path(), "notes.txt");
        fs::create_dir(dir.path().join("folder.cbz")).unwrap(); // a folder, not a file

        assert_eq!(find_cbz(dir.path(), false), [upper, b, nested]);
    }

    #[test]
    fn recent_only_skips_old_files() {
        let dir = tempfile::tempdir().unwrap();
        let fresh = touch(dir.path(), "fresh.cbz");
        let old = touch(dir.path(), "old.cbz");
        let thirty_days_ago = SystemTime::now() - Duration::from_secs(30 * SECONDS_PER_DAY);
        File::options()
            .write(true)
            .open(&old)
            .unwrap()
            .set_modified(thirty_days_ago)
            .unwrap();

        assert_eq!(find_cbz(dir.path(), true), std::slice::from_ref(&fresh));
        assert_eq!(find_cbz(dir.path(), false), [fresh, old]);
    }

    #[test]
    fn subdirectories_lists_only_folders_sorted() {
        let dir = tempfile::tempdir().unwrap();
        fs::create_dir(dir.path().join("b")).unwrap();
        fs::create_dir(dir.path().join("a")).unwrap();
        touch(dir.path(), "file.txt");

        let names: Vec<String> = subdirectories(dir.path())
            .unwrap()
            .iter()
            .map(|path| display_name(path))
            .collect();
        assert_eq!(names, ["a", "b"]);
    }
}