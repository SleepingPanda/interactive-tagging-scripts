//! Fixing ownership and permissions after tagging (Unix only).
//!
//! ComicTagger rewrites each `.cbz`, so the new files may end up owned by whichever user ran
//! the tool. Servers that read the library (Kavita, for example) usually need the files to
//! belong to a specific account, so after tagging we hand the series folder back to it.
//!
//! On non-Unix platforms (Windows) this step does nothing.

#[cfg(unix)]
pub use unix::fix_permissions;

/// Does nothing on non-Unix platforms.
#[cfg(not(unix))]
pub fn fix_permissions(_directory: &std::path::Path) {}

#[cfg(unix)]
mod unix {
    use std::fs;
    use std::io;
    use std::os::unix::fs::{chown, PermissionsExt};
    use std::path::Path;

    use log::warn;
    use walkdir::WalkDir;

    use crate::library::is_cbz_file;

    // These three values are the ones to change to suit your setup.
    /// User ID that should own the library. 1000 is typically the first regular user on Linux.
    const OWNER_UID: u32 = 1000;
    /// Group ID that should own the library.
    const OWNER_GID: u32 = 1000;
    /// Permission bits for `.cbz` files: owner read/write, everyone else read-only.
    const FILE_MODE: u32 = 0o644;

    /// Gives everything in `directory` to [`OWNER_UID`]:[`OWNER_GID`] and sets the mode of
    /// its `.cbz` files to [`FILE_MODE`].
    ///
    /// A failure (for example, not being allowed to change ownership) is logged as a warning
    /// and never stops the run: the files are already tagged at this point.
    pub fn fix_permissions(directory: &Path) {
        if let Err(error) = apply(directory) {
            warn!(
                "Permission update failed for '{}': {error}",
                directory.display()
            );
        }
    }

    /// Does the actual work for [`fix_permissions`], stopping at the first error.
    fn apply(directory: &Path) -> io::Result<()> {
        // `min_depth(1)` skips the directory itself; it is handled after its contents.
        for entry in WalkDir::new(directory).min_depth(1) {
            let path = entry?.into_path();
            chown(&path, Some(OWNER_UID), Some(OWNER_GID))?;
            if is_cbz_file(&path) {
                fs::set_permissions(&path, fs::Permissions::from_mode(FILE_MODE))?;
            }
        }
        chown(directory, Some(OWNER_UID), Some(OWNER_GID))
    }
}