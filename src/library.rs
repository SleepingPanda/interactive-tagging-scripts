//! Filesystem helpers: finding series folders and .cbz files, fixing permissions.

use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};

use log::warn;
use walkdir::WalkDir;

const RECENT_DAYS: u64 = 14;
#[cfg(unix)]
const OWNER_UID: u32 = 1000;
#[cfg(unix)]
const OWNER_GID: u32 = 1000;
#[cfg(unix)]
const FILE_MODE: u32 = 0o644;

/// The last path component as text (the series name for a series folder).
pub fn dir_name(path: &Path) -> String {
    path.file_name().unwrap_or_default().to_string_lossy().into_owned()
}

/// Immediate subdirectories of `root`, sorted.
pub fn subdirectories(root: &Path) -> Result<Vec<PathBuf>, String> {
    let mut dirs: Vec<PathBuf> = fs::read_dir(root)
        .map_err(|e| format!("Cannot read '{}': {e}", root.display()))?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|p| p.is_dir())
        .collect();
    dirs.sort();
    Ok(dirs)
}

fn is_cbz(path: &Path) -> bool {
    path.extension().is_some_and(|e| e.eq_ignore_ascii_case("cbz"))
}

/// Recursively list .cbz files (sorted), optionally only recently modified ones.
pub fn find_cbz(directory: &Path, recent_only: bool) -> Vec<PathBuf> {
    let cutoff = SystemTime::now() - Duration::from_secs(RECENT_DAYS * 86_400);
    let mut files: Vec<PathBuf> = WalkDir::new(directory)
        .into_iter()
        .filter_map(|entry| entry.map_err(|e| warn!("{e}")).ok())
        .map(|entry| entry.into_path())
        .filter(|p| is_cbz(p) && p.is_file())
        .filter(|p| {
            !recent_only || fs::metadata(p).and_then(|m| m.modified()).is_ok_and(|t| t >= cutoff)
        })
        .collect();
    files.sort();
    files
}

/// Chown the series directory tree and chmod its .cbz files.
#[cfg(unix)]
pub fn fix_permissions(directory: &Path) {
    use std::os::unix::fs::{chown, PermissionsExt};

    let result = (|| -> io::Result<()> {
        for entry in WalkDir::new(directory).min_depth(1) {
            let path = entry?.into_path();
            chown(&path, Some(OWNER_UID), Some(OWNER_GID))?;
            if is_cbz(&path) && path.is_file() {
                fs::set_permissions(&path, fs::Permissions::from_mode(FILE_MODE))?;
            }
        }
        chown(directory, Some(OWNER_UID), Some(OWNER_GID))
    })();
    if let Err(e) = result {
        warn!("Permission update failed for '{}': {e}", directory.display());
    }
}

#[cfg(not(unix))]
pub fn fix_permissions(_directory: &Path) {}