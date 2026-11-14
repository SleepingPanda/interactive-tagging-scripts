//! The JSON5 metadata file, and the `key=value,...` string that tells ComicTagger what to write.

use std::collections::HashMap;
use std::fs;
use std::io;
use std::path::Path;

use anyhow::{anyhow, Context, Result};
use indexmap::IndexMap;
use serde::Deserialize;

/// Use this figure for Kavita to recognize the tagged file as a single volume instead of as a chapter/issue.
const ISSUE_SENTINEL: i32 = -100_000;

/// All known series, keyed by the exact name of the series' directory.
pub type Catalog = HashMap<String, Series>;

/// Metadata for one series, as written in the metadata file.
///
/// The field names are the keys used in the file. Any field left out of the file falls back
/// to its default (empty text, `false`, empty list) thanks to `#[serde(default)]`, and keys
/// this struct does not know about are ignored.
#[derive(Debug, Default, Deserialize)]
#[serde(default)]
pub struct Series {
    /// Whether the series is manga (as opposed to western comics).
    manga: bool,
    /// Whether the pages are black and white.
    black_and_white: bool,
    language: String,
    genre: String,
    maturity_rating: String,
    publisher: String,
    imprint: String,
    series: String,
    /// Groups related series (e.g. several parts of one franchise) together.
    series_group: String,
    web_link: String,
    /// Role -> person, e.g. `Writer: "Jane Doe"`. An `IndexMap` keeps the order of the file.
    credit: IndexMap<String, String>,
    characters: Vec<String>,
}

impl Series {
    /// The plain-text fields as `(ComicTagger key, value)` pairs, in the order they are
    /// passed to ComicTagger.
    fn text_fields(&self) -> [(&'static str, &str); 8] {
        [
            ("language", &self.language),
            ("genre", &self.genre),
            ("maturity_rating", &self.maturity_rating),
            ("publisher", &self.publisher),
            ("imprint", &self.imprint),
            ("series", &self.series),
            ("series_group", &self.series_group),
            ("web_link", &self.web_link),
        ]
    }
}

/// The shape of the whole file: one top-level `Manga` key containing every series.
#[derive(Deserialize)]
struct MetadataFile {
    #[serde(rename = "Manga")]
    manga: Catalog,
}

/// Reads and parses the metadata file, returning its `Manga` section.
///
/// The error messages are shown to the user as-is, so they name the file involved.
pub fn load_metadata(path: &Path) -> Result<Catalog> {
    let text = fs::read_to_string(path).map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            anyhow!("Metadata file '{}' not found.", path.display())
        } else {
            anyhow::Error::new(error).context(format!("Failed to read '{}'", path.display()))
        }
    })?;
    let file: MetadataFile =
        json5::from_str(&text).with_context(|| format!("Failed to parse '{}'", path.display()))?;
    Ok(file.manga)
}

/// Escapes `,` and `=` with a `^`, because ComicTagger uses them as delimiters in its
/// `key=value,key=value` argument.
fn escape(value: &str) -> String {
    value.replace(',', "^,").replace('=', "^=")
}

fn yes_no(flag: bool) -> &'static str {
    if flag {
        "Yes"
    } else {
        "No"
    }
}

/// Builds the value for ComicTagger's `-m` option: a comma-separated list of `key=value`
/// pairs. For example (shortened):
///
/// ```text
/// manga=Yes,issue=-100000,black_and_white=Yes,language=en,...,volume=3,title=Volume 3,year=2021,credit=Writer:Jane Doe,characters=A^,B
/// ```
///
/// `volume` and `year` come from the filename (see the `filename` module); each is left out
/// when `None`.
pub fn build_metadata_string(meta: &Series, volume: Option<u32>, year: Option<u32>) -> String {
    let mut pairs = vec![
        format!("manga={}", yes_no(meta.manga)),
        format!("issue={ISSUE_SENTINEL}"),
        format!("black_and_white={}", yes_no(meta.black_and_white)),
    ];

    pairs.extend(
        meta.text_fields()
            .iter()
            .map(|(key, value)| format!("{key}={}", escape(value))),
    );

    if let Some(volume) = volume {
        pairs.push(format!("volume={volume}"));
        pairs.push(format!("title=Volume {volume}"));
    }
    if let Some(year) = year {
        pairs.push(format!("year={year}"));
    }

    // One `credit=Role:Person` pair per entry.
    pairs.extend(
        meta.credit
            .iter()
            .map(|(role, person)| format!("credit={role}:{}", escape(person))),
    );

    // All characters go into a single `characters=` value. Items are joined with an
    // escaped comma (`^,`) so ComicTagger reads them as one list rather than as separate
    // key=value pairs. Note that a comma *inside* a name is escaped the same way, so it is
    // indistinguishable from the separator (behavior carried over from the original script).
    if !meta.characters.is_empty() {
        let names: Vec<String> = meta.characters.iter().map(|name| escape(name)).collect();
        pairs.push(format!("characters={}", names.join("^,")));
    }

    pairs.join(",")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn escaping_and_assembly() {
        let meta = Series {
            manga: true,
            language: "en".into(),
            series: "A, B=C".into(),
            characters: vec!["X".into(), "Y".into()],
            credit: IndexMap::from([("Writer".into(), "W".into()), ("Cover".into(), "C".into())]),
            ..Series::default()
        };
        assert_eq!(
            build_metadata_string(&meta, Some(3), Some(2021)),
            "manga=Yes,issue=-100000,black_and_white=No,language=en,genre=,maturity_rating=,\
             publisher=,imprint=,series=A^, B^=C,series_group=,web_link=,volume=3,title=Volume 3,\
             year=2021,credit=Writer:W,credit=Cover:C,characters=X^,Y"
        );
        assert!(!build_metadata_string(&meta, None, None).contains("volume="));
    }

    #[test]
    fn json5_features() {
        let text = r#"
            // comment
            /* block */
            { Manga: { 'Foo': {
                manga: true,
                characters: ['A', "B",],
                credit: { Writer: 'X', Cover: "Y", },
                unknown_field: 1,
            }, }, }
        "#;
        let file: MetadataFile = json5::from_str(text).unwrap();
        let foo = &file.manga["Foo"];
        assert!(foo.manga && !foo.black_and_white);
        assert_eq!(foo.characters, ["A", "B"]);
        // Credit order follows the file, not alphabetical order.
        assert_eq!(foo.credit.keys().collect::<Vec<_>>(), ["Writer", "Cover"]);
    }

    #[test]
    fn plain_json_still_parses() {
        let file: MetadataFile = json5::from_str(r#"{"Manga": {"X": {"manga": true}}}"#).unwrap();
        assert!(file.manga["X"].manga);
    }

    #[test]
    fn load_metadata_error_messages() {
        let dir = tempfile::tempdir().unwrap();

        let missing = dir.path().join("nope.json5");
        let message = load_metadata(&missing).unwrap_err().to_string();
        assert_eq!(
            message,
            format!("Metadata file '{}' not found.", missing.display())
        );

        let broken = dir.path().join("broken.json5");
        fs::write(&broken, "{ Manga: { ").unwrap();
        let message = format!("{:#}", load_metadata(&broken).unwrap_err());
        assert!(message.starts_with(&format!("Failed to parse '{}': ", broken.display())));
    }
}