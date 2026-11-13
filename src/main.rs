//! Batch-tag manga CBZ files with ComicTagger using a JSON5 metadata file.
//!
//! Metadata file layout:
//!     { Manga: { "<series directory name>": { ...series fields... } } }
//!
//! Usage:
//!     dirtag                          # interactive mode
//!     dirtag -a                       # tag every series subdirectory
//!     dirtag -a -r                    # only files modified in the last 14 days
//!     dirtag -m meta.json5 -d /library

mod filename;
mod interactive;
mod library;
mod logger;
mod metadata;
mod tagger;

use std::path::PathBuf;
use std::process::ExitCode;

use clap::Parser;
use log::info;

const DEFAULT_METADATA: &str = "manga.json5";

#[derive(Parser)]
#[command(about = "Batch tag manga CBZ files with ComicTagger.")]
struct Args {
    /// Metadata JSON5 path
    #[arg(short, long, default_value = DEFAULT_METADATA)]
    metadata: PathBuf,

    /// Root directory containing series subdirectories
    #[arg(short, long, default_value = ".")]
    directory: PathBuf,

    /// Only process .cbz files modified in the last 14 days
    #[arg(short, long)]
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

fn run() -> Result<(), String> {
    let args = Args::parse();
    logger::init(args.verbose);

    which::which("comictagger").map_err(|_| "'comictagger' was not found on PATH.".to_string())?;
    if !args.directory.is_dir() {
        return Err(format!("Directory '{}' does not exist.", args.directory.display()));
    }
    let book = metadata::load_metadata(&args.metadata)?;
    let subdirs = library::subdirectories(&args.directory)?;
    if subdirs.is_empty() {
        return Err(format!("No subdirectories found in '{}'.", args.directory.display()));
    }

    let perms = !args.no_perms;
    if args.all {
        for dir in &subdirs {
            tagger::process_series(dir, &book, args.recent, perms);
        }
        info!("Finished processing all directories.");
    } else {
        interactive::run(&subdirs, &book, perms);
    }
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("{message}");
            ExitCode::FAILURE
        }
    }
}