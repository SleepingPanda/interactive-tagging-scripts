//! Pulling the volume number and publication year out of a `.cbz` filename.
//!
//! Example: `My Series v03 (2021).cbz` -> volume 3, year 2021.

use std::sync::LazyLock;

use log::warn;
use regex::Regex;

/// Matches `v1`, `v01`, `Vol.2`, `vol 3`, ... (case-insensitive) and captures the digits.
///
/// `\b` is a "word boundary": it stops the pattern from matching a `v` in the middle of a
/// word, so `Revolution 5` does not count as volume 5.
static VOLUME_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\bv(?:ol\.?\s*)?([0-9]+)\b").expect("volume pattern is valid")
});

/// Matches a four-digit year in parentheses, such as `(2023)`, and captures the digits.
static YEAR_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\(([0-9]{4})\)").expect("year pattern is valid"));

/// Returns the first number captured by `pattern` in `filename`.
///
/// Logs a warning naming `what` (e.g. "year") and returns `None` when the filename has no
/// match. The tag for that field is then simply left out.
fn extract_number(pattern: &Regex, filename: &str, what: &str) -> Option<u32> {
    let number = pattern
        .captures(filename)
        // Group 0 is the whole match; group 1 is the digits we asked to capture.
        .and_then(|captures| captures[1].parse().ok());
    if number.is_none() {
        warn!("Could not extract {what} from '{filename}'.");
    }
    number
}

/// The volume number in a filename, e.g. `v01` or `Vol.2`.
pub fn parse_volume(filename: &str) -> Option<u32> {
    extract_number(&VOLUME_RE, filename, "volume number")
}

/// The year in a filename, e.g. `(2023)`.
pub fn parse_year(filename: &str) -> Option<u32> {
    extract_number(&YEAR_RE, filename, "year")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn volume_forms() {
        assert_eq!(parse_volume("Series v01 (2023).cbz"), Some(1));
        assert_eq!(parse_volume("Series Vol.2.cbz"), Some(2));
        assert_eq!(parse_volume("Series VOL. 13.cbz"), Some(13));
        assert_eq!(parse_volume("Series Vol 7 (2020).cbz"), Some(7));
    }

    #[test]
    fn volume_missing_or_not_a_volume() {
        assert_eq!(parse_volume("Series (2023).cbz"), None);
        assert_eq!(parse_volume("Series.cbz"), None);
        // A "v" inside a word must not be mistaken for a volume marker.
        assert_eq!(parse_volume("Revolution 5.cbz"), None);
    }

    #[test]
    fn year_forms() {
        assert_eq!(parse_year("Series v01 (2023).cbz"), Some(2023));
        assert_eq!(parse_year("Series v01 (23).cbz"), None);
        assert_eq!(parse_year("Series v01 2023.cbz"), None);
    }
}