//! Batch-tag manga CBZ files with ComicTagger using a JSON5 metadata file.
//!
//! Metadata file layout:
//!
//! ```text
//! { Manga: { "<series directory name>": { ...series fields... } } }
//! ```
//!
//! Usage:
//!
//! ```text
//! dirtag                          # interactive mode
//! dirtag -a                       # tag every series subdirectory
//! dirtag -a -r                    # only files modified in the last 14 days
//! dirtag -m meta.json5 -d /library
//! ```
//!
//! How the pieces fit together:
//!   - `metadata`    loads the metadata file and builds ComicTagger's `-m` argument
//!   - `library`     finds series folders and `.cbz` files on disk
//!   - `filename`    reads the volume number and year out of file names
//!   - `tagger`      runs ComicTagger on each file of a series
//!   - `permissions` fixes ownership/permissions after tagging (Unix only)
//!   - `interactive` the menu used when `--all` is not given
//!   - `logger`      colored log output

mod filename;
mod interactive;
mod library;
mod logger;
mod metadata;
mod permissions;
mod tagger;

use std::path::PathBuf;
use std::process::ExitCode;

use anyhow::{bail, Result};
use clap::Parser;
use log::info;

use crate::tagger::TagOptions;

const DEFAULT_METADATA: &str = "manga.json5";

/// Command-line options. `clap` generates the parsing and the `--help` text from this
/// struct; the `///` comment on each field becomes its help line.
#[derive(Parser)]
#[command(about = "Batch tag manga CBZ files with ComicTagger.")]
struct Args {
    /// Metadata JSON5 path
    #[arg(short, long, default_value = DEFAULT_METADATA)]
    metadata: PathBuf,

    /// Root directory containing series subdirectories
    #[arg(short, long, default_value = ".")]
    directory: PathBuf,

    // Written as an expression (not a `///` comment) so the number of days is not repeated.
    #[arg(
        short,
        long,
        help = format!(
            "Only process .cbz files modified in the last {} days",
            library::RECENT_DAYS
        )
    )]
    recent: bool,

    /// Process every subdirectory without prompting
    #[arg(short, long)]
    all: bool,

    /// Skip chown/chmod after tagging
    #[arg(long)]
    no_perms: bool,

    /// Enable DEBUG output
    #[arg(short, long)]
    verbose: bool,
}

/// The program proper. Any error returned here is printed by `main` and ends the run.
fn run() -> Result<()> {
    let args = Args::parse();
    logger::init(args.verbose);

    // Check everything we can up front, so the user is not asked questions that could
    // never lead anywhere.
    tagger::ensure_comictagger_installed()?;
    if !args.directory.is_dir() {
        bail!("Directory '{}' does not exist.", args.directory.display());
    }
    let catalog = metadata::load_metadata(&args.metadata)?;
    let series_dirs = library::subdirectories(&args.directory)?;
    if series_dirs.is_empty() {
        bail!("No subdirectories found in '{}'.", args.directory.display());
    }

    let options = TagOptions {
        recent_only: args.recent,
        fix_permissions: !args.no_perms,
    };
    if args.all {
        for directory in &series_dirs {
            tagger::process_series(directory, &catalog, options);
        }
        info!("Finished processing all directories.");
    } else {
        interactive::run(&series_dirs, &catalog, options);
    }
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            // `{:#}` prints the whole chain of causes on one line ("what we were doing: why
            // it failed"), which is how the messages built with `with_context` read best.
            eprintln!("{error:#}");
            ExitCode::FAILURE
        }
    }
}