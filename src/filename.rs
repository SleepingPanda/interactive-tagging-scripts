//! Extract the volume number and year from a .cbz filename.

use std::sync::OnceLock;

use log::warn;
use regex::Regex;

fn volume_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?i)\bv(?:ol\.?\s*)?([0-9]+)\b").unwrap())
}

fn year_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\(([0-9]{4})\)").unwrap())
}

fn capture_number(re: &Regex, filename: &str) -> Option<u32> {
    re.captures(filename)?.get(1)?.as_str().parse().ok()
}

/// Volume number in a filename such as `v01` or `Vol.2`.
pub fn parse_volume(filename: &str) -> Option<u32> {
    let volume = capture_number(volume_re(), filename);
    if volume.is_none() {
        warn!("Could not extract volume number from '{filename}'.");
    }
    volume
}

/// Year in a filename such as `(2023)`.
pub fn parse_year(filename: &str) -> Option<u32> {
    let year = capture_number(year_re(), filename);
    if year.is_none() {
        warn!("Could not extract year from '{filename}'.");
    }
    year
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
        assert_eq!(parse_volume("Series (2023).cbz"), None);
        assert_eq!(parse_volume("Series.cbz"), None);
    }

    #[test]
    fn year_forms() {
        assert_eq!(parse_year("Series v01 (2023).cbz"), Some(2023));
        assert_eq!(parse_year("Series v01 (23).cbz"), None);
        assert_eq!(parse_year("Series v01 2023.cbz"), None);
    }
}