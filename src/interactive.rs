//! Interactive mode: choose a series from a numbered menu, one at a time.

use std::io::{self, Write};
use std::path::{Path, PathBuf};

use colored::Colorize;
use log::info;

use crate::library::display_name;
use crate::metadata::Catalog;
use crate::tagger::{process_series, TagOptions};

/// Shows `text` as a prompt and reads one line from the user.
///
/// The answer comes back trimmed and lowercased, so callers can compare it with plain
/// strings. Returns `None` when input has ended (Ctrl-D / end of a pipe), which callers
/// treat as "stop asking".
fn prompt(text: &str) -> Option<String> {
    print!("{}", text.red());
    // `print!` does not end the line, so the text may sit in a buffer; flush to show it now.
    io::stdout().flush().ok();

    let mut line = String::new();
    match io::stdin().read_line(&mut line) {
        // Zero bytes read means end of input. Move to a fresh line so later output is tidy.
        Ok(0) | Err(_) => {
            println!();
            None
        }
        Ok(_) => Some(line.trim().to_lowercase()),
    }
}

/// Prints the numbered list of directories, starting at 1.
fn print_menu(directories: &[PathBuf]) {
    println!("{}", "Available directories:".yellow());
    for (number, directory) in (1..).zip(directories) {
        println!(
            "  {} {}",
            format!("{number}.").red(),
            display_name(directory).green()
        );
    }
}

/// Turns a typed menu number (1-based) into a list index (0-based).
/// Returns `None` unless `input` is a whole number from 1 to `item_count`.
fn parse_menu_choice(input: &str, item_count: usize) -> Option<usize> {
    let number: usize = input.parse().ok()?;
    (1..=item_count).contains(&number).then(|| number - 1)
}

/// Shows the menu until the user picks a directory.
///
/// Returns `None` if the user quits with `q` or input ends.
fn choose_directory(directories: &[PathBuf]) -> Option<&Path> {
    loop {
        print_menu(directories);
        let input = prompt("Choose a directory # or 'q' to quit: ")?;
        if input == "q" {
            return None;
        }
        match parse_menu_choice(&input, directories.len()) {
            Some(index) => return Some(&directories[index]),
            None => println!(
                "{}",
                format!(
                    "Invalid choice. Enter a number from 1 to {}, or 'q'.",
                    directories.len()
                )
                .red()
            ),
        }
    }
}

/// Asks a yes/no question. Anything starting with `y` counts as yes.
/// Returns `None` when input has ended.
fn ask_yes_no(question: &str) -> Option<bool> {
    prompt(&format!("{question} (y/n): ")).map(|answer| answer.starts_with('y'))
}

/// Repeatedly lets the user pick a series and tags it, until they quit.
///
/// Whether to tag only recent files is asked for each series, so it overrides
/// `options.recent_only` (the `--recent` flag is ignored in this mode).
pub fn run(series_dirs: &[PathBuf], catalog: &Catalog, options: TagOptions) {
    while let Some(selected) = choose_directory(series_dirs) {
        let question = format!("Process only recent files in '{}'?", display_name(selected));
        // Input ended while answering: stop instead of tagging with a guessed answer.
        let Some(recent_only) = ask_yes_no(&question) else {
            break;
        };
        process_series(
            selected,
            catalog,
            TagOptions {
                recent_only,
                ..options
            },
        );
    }
    info!("Finished manual processing.");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn menu_choice_is_one_based_and_range_checked() {
        assert_eq!(parse_menu_choice("1", 3), Some(0));
        assert_eq!(parse_menu_choice("3", 3), Some(2));
        assert_eq!(parse_menu_choice("0", 3), None);
        assert_eq!(parse_menu_choice("4", 3), None);
        assert_eq!(parse_menu_choice("abc", 3), None);
        assert_eq!(parse_menu_choice("", 3), None);
        assert_eq!(parse_menu_choice("-1", 3), None);
    }
}