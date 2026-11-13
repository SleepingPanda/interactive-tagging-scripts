//! Interactive mode: pick a series from a numbered menu.

use std::io::{self, Write};
use std::path::{Path, PathBuf};

use colored::Colorize;
use log::info;

use crate::library::dir_name;
use crate::metadata::Book;
use crate::tagger::process_series;

/// Print a prompt and read a trimmed, lowercased line. `None` on EOF.
fn prompt(text: &str) -> Option<String> {
    print!("{}", text.red());
    io::stdout().flush().ok();
    let mut line = String::new();
    match io::stdin().read_line(&mut line) {
        Ok(0) | Err(_) => {
            println!();
            None
        }
        Ok(_) => Some(line.trim().to_lowercase()),
    }
}

/// Prompt until the user picks a directory number; `None` on 'q' or EOF.
fn choose_directory(dirs: &[PathBuf]) -> Option<&Path> {
    loop {
        println!("{}", "Available directories:".yellow());
        for (i, d) in dirs.iter().enumerate() {
            println!("  {} {}", format!("{}.", i + 1).red(), dir_name(d).green());
        }
        let raw = prompt("Choose a directory # or 'q' to quit: ")?;
        if raw == "q" {
            return None;
        }
        match raw.parse::<usize>() {
            Ok(n) if (1..=dirs.len()).contains(&n) => return Some(&dirs[n - 1]),
            _ => println!(
                "{}",
                format!("Invalid choice. Enter a number from 1 to {}, or 'q'.", dirs.len()).red()
            ),
        }
    }
}

fn ask_yes_no(question: &str) -> Option<bool> {
    prompt(&format!("{question} (y/n): ")).map(|a| a.starts_with('y'))
}

pub fn run(subdirs: &[PathBuf], book: &Book, perms: bool) {
    while let Some(selected) = choose_directory(subdirs) {
        let question = format!("Process only recent files in '{}'?", dir_name(selected));
        let Some(recent) = ask_yes_no(&question) else {
            break;
        };
        process_series(selected, book, recent, perms);
    }
    info!("Finished manual processing.");
}