//! The JSON5 metadata file and the string handed to `comictagger -m`.

use std::collections::HashMap;
use std::fs;
use std::io;
use std::path::Path;

use indexmap::IndexMap;
use serde::Deserialize;

/// Use this figure for Kavita to recognize the tagged file as a single volume instead of as a chapter/issue.
const ISSUE_SENTINEL: i32 = -100_000;

/// Series directory name -> that series' metadata.
pub type Book = HashMap<String, Series>;

#[derive(Debug, Default, Deserialize)]
#[serde(default)]
pub struct Series {
    manga: bool,
    black_and_white: bool,
    language: String,
    genre: String,
    maturity_rating: String,
    publisher: String,
    imprint: String,
    series: String,
    series_group: String,
    web_link: String,
    credit: IndexMap<String, String>,
    characters: Vec<String>,
}

#[derive(Deserialize)]
struct MetadataFile {
    #[serde(rename = "Manga")]
    manga: Book,
}

/// Load the `Manga` section of the JSON5 metadata file.
pub fn load_metadata(path: &Path) -> Result<Book, String> {
    let text = fs::read_to_string(path).map_err(|e| match e.kind() {
        io::ErrorKind::NotFound => format!("Metadata file '{}' not found.", path.display()),
        _ => format!("Failed to read '{}': {e}", path.display()),
    })?;
    let file: MetadataFile = json5::from_str(&text)
        .map_err(|e| format!("Failed to parse '{}': {e}", path.display()))?;
    Ok(file.manga)
}

/// Escape `,` and `=`, which ComicTagger treats as delimiters.
fn esc(value: &str) -> String {
    value.replace(',', "^,").replace('=', "^=")
}

fn yn(flag: bool) -> &'static str {
    if flag {
        "Yes"
    } else {
        "No"
    }
}

/// Build the comma-delimited key=value string for `comictagger -m`.
pub fn build_metadata_string(meta: &Series, volume: Option<u32>, year: Option<u32>) -> String {
    let text_fields = [
        ("language", &meta.language),
        ("genre", &meta.genre),
        ("maturity_rating", &meta.maturity_rating),
        ("publisher", &meta.publisher),
        ("imprint", &meta.imprint),
        ("series", &meta.series),
        ("series_group", &meta.series_group),
        ("web_link", &meta.web_link),
    ];

    let mut parts = vec![
        format!("manga={}", yn(meta.manga)),
        format!("issue={ISSUE_SENTINEL}"),
        format!("black_and_white={}", yn(meta.black_and_white)),
    ];
    parts.extend(text_fields.iter().map(|(key, value)| format!("{key}={}", esc(value))));
    if let Some(v) = volume {
        parts.push(format!("volume={v}"));
        parts.push(format!("title=Volume {v}"));
    }
    if let Some(y) = year {
        parts.push(format!("year={y}"));
    }
    parts.extend(
        meta.credit
            .iter()
            .map(|(role, person)| format!("credit={role}:{}", esc(person))),
    );
    if !meta.characters.is_empty() {
        let names: Vec<String> = meta.characters.iter().map(|c| esc(c)).collect();
        parts.push(format!("characters={}", names.join("^,")));
    }
    parts.join(",")
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
}