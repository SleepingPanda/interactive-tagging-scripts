//! Colored, level-tagged logging to stderr.

use colored::Colorize;
use log::{Level, LevelFilter, Metadata, Record};

struct Logger;

impl log::Log for Logger {
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
            level => format!("[{level}]").cyan(),
        };
        eprintln!("{tag} {}", record.args());
    }

    fn flush(&self) {}
}

static LOGGER: Logger = Logger;

/// Install the logger; `verbose` enables DEBUG output.
pub fn init(verbose: bool) {
    #[cfg(windows)]
    let _ = colored::control::set_virtual_terminal(true);
    let _ = log::set_logger(&LOGGER);
    log::set_max_level(if verbose { LevelFilter::Debug } else { LevelFilter::Info });
}