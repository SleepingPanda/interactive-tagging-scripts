//! Logging setup.
//!
//! The rest of the program logs through the standard `log` macros (`info!`, `warn!`, ...).
//! This module decides what happens to those messages: they are printed to stderr with a
//! colored `[LEVEL]` tag in front.

use colored::Colorize;
use log::{Level, LevelFilter, Metadata, Record};

/// A minimal logger that prints `[LEVEL] message` to stderr.
struct ColorLogger;

impl log::Log for ColorLogger {
    fn enabled(&self, metadata: &Metadata) -> bool {
        metadata.level() <= log::max_level()
    }

    fn log(&self, record: &Record) {
        if !self.enabled(record.metadata()) {
            return;
        }
        let tag = match record.level() {
            Level::Error => "[ERROR]".red(),
            Level::Warn => "[WARNING]".yellow(),
            // INFO, DEBUG and TRACE all share one calm color.
            level => format!("[{level}]").cyan(),
        };
        eprintln!("{tag} {}", record.args());
    }

    fn flush(&self) {}
}

/// `log::set_logger` needs a reference that lives for the whole program.
static LOGGER: ColorLogger = ColorLogger;

/// Install the logger. Call once, at startup.
///
/// With `verbose` set, DEBUG messages are shown too; otherwise only INFO and above.
/// (The `colored` crate disables colors by itself when output is not a terminal or when
/// the `NO_COLOR` environment variable is set.)
pub fn init(verbose: bool) {
    // Older Windows consoles need ANSI color support switched on explicitly.
    #[cfg(windows)]
    let _ = colored::control::set_virtual_terminal(true);

    // `set_logger` only fails if a logger is already installed, which cannot happen here.
    let _ = log::set_logger(&LOGGER);
    log::set_max_level(if verbose {
        LevelFilter::Debug
    } else {
        LevelFilter::Info
    });
}