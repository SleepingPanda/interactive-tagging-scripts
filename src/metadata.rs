//! The JSON5 metadata file, and the `key=value,...` string that tells ComicTagger what to write.
//! # File layout
//! ```text
//! {
//!     Defaults: { ... },               // optional: fallback values for every series
//!     Series: {                        // required (`Manga` is accepted as an older name)
//!         "<series directory name>": { ... },
//!     },
//! }
//! ```
//! Each series is matched to its folder by exact name.
//! For every field, the value used is the first one found of: the series' own entry, then `Defaults`, then empty/`false`.

use std::collections::HashMap;
use std::fs;
use std::io;
use std::path::Path;

use anyhow::{anyhow, Context, Result};
use indexmap::IndexMap;
use serde::{Deserialize, Deserializer};

/// Use this figure for Kavita to recognize the tagged file as a single volume instead of as a chapter/issue.
const ISSUE_SENTINEL: i32 = -100_000;

/// All known series, keyed by the exact name of the series' directory.
pub type Catalog = HashMap<String, Series>;

/// Metadata for one series with every default already applied: what gets written to its files.
/// Built from the file by [`SeriesFields::resolve`].
#[derive(Debug, Default)]
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
    /// Role -> person, one entry per role, in the order written.
    credit: IndexMap<String, String>,
    characters: Vec<String>,
}

impl Series {
    /// The plain-text fields as `(ComicTagger key, value)` pairs, in the order they are passed to ComicTagger.
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

/// The fields of a series exactly as written in the metadata file.
/// The same shape is used for a series entry and for `Defaults`.
/// Every field is optional so that "left out" can be told apart from "set to empty": a series that leaves a field out inherits it from `Defaults`, while one that sets it to `""` deliberately clears it.
/// Keys this struct does not know about are ignored.
#[derive(Debug, Default, Deserialize)]
#[serde(default)]
struct SeriesFields {
    /// Whether the series is manga (read right-to-left) rather than a western comic.
    manga: Option<bool>,
    /// Whether the pages are black and white.
    black_and_white: Option<bool>,
    language: Option<String>,
    genre: Option<String>,
    maturity_rating: Option<String>,
    publisher: Option<String>,
    imprint: Option<String>,
    series: Option<String>,
    /// Groups related series (e.g. several parts of one franchise) together.
    series_group: Option<String>,
    web_link: Option<String>,
    /// Role -> person, e.g. `Writer: "Jane Doe"`.
    /// A key may list several comma-separated roles that share one person: `"Cover, Inker, Penciller": "Jane Doe"`.
    #[serde(deserialize_with = "deserialize_credit")]
    credit: IndexMap<String, String>,
    characters: Option<Vec<String>>,
}

impl SeriesFields {
    /// Layers this series' own values over `defaults`.
    /// - Single values: the series' value wins; if it left the field out, the default is used.
    /// - `credit`: merged role by role.
    /// A series can override one role and keep the rest.
    /// An overridden role keeps the position it had in the defaults.
    /// - `characters`: a list is replaced as a whole, never merged.
    fn resolve(self, defaults: &SeriesFields) -> Series {
        let mut credit = defaults.credit.clone();
        credit.extend(self.credit);

        Series {
            manga: pick(self.manga, &defaults.manga),
            black_and_white: pick(self.black_and_white, &defaults.black_and_white),
            language: pick(self.language, &defaults.language),
            genre: pick(self.genre, &defaults.genre),
            maturity_rating: pick(self.maturity_rating, &defaults.maturity_rating),
            publisher: pick(self.publisher, &defaults.publisher),
            imprint: pick(self.imprint, &defaults.imprint),
            series: pick(self.series, &defaults.series),
            series_group: pick(self.series_group, &defaults.series_group),
            web_link: pick(self.web_link, &defaults.web_link),
            credit,
            characters: pick(self.characters, &defaults.characters),
        }
    }
}

/// `own` if it was set, else `default` if that was set, else the type's empty value.
fn pick<T: Clone + Default>(own: Option<T>, default: &Option<T>) -> T {
    own.or_else(|| default.clone()).unwrap_or_default()
}

/// Reads a `credit` table and splits keys like `"Cover, Inker"` into one entry per role.
fn deserialize_credit<'de, D>(deserializer: D) -> Result<IndexMap<String, String>, D::Error>
where
    D: Deserializer<'de>,
{
    let grouped = IndexMap::<String, String>::deserialize(deserializer)?;
    expand_role_groups(grouped).map_err(serde::de::Error::custom)
}

/// Turns `{"Cover, Inker": "A", "Writer": "B"}` into `{"Cover": "A", "Inker": "A", "Writer": "B"}`.
/// Roles keep the order they were written in. If a role is named twice, the later entry wins but keeps the earlier position.
/// An empty role name (e.g. a stray comma) is an error, because it would otherwise be sent to ComicTagger as a blank role.
fn expand_role_groups(
    grouped: IndexMap<String, String>,
) -> Result<IndexMap<String, String>, String> {
    let mut credit = IndexMap::new();
    for (roles, person) in grouped {
        for role in roles.split(',').map(str::trim) {
            if role.is_empty() {
                return Err(format!("credit key '{roles}' contains an empty role name"));
            }
            credit.insert(role.to_string(), person.clone());
        }
    }
    Ok(credit)
}

/// The shape of the whole file.
/// Unknown top-level keys are rejected.
/// Unlike unknown series fields, silently ignoring them would hide a misspelled `Defaults` and leave the whole library tagged without it.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct MetadataFile {
    #[serde(rename = "Defaults", default)]
    defaults: SeriesFields,
    /// `Manga` is the older name for this key and is still accepted.
    #[serde(rename = "Series", alias = "Manga")]
    series: HashMap<String, SeriesFields>,
}

/// Parses the text of a metadata file and applies `Defaults` to every series.
fn parse_catalog(text: &str) -> Result<Catalog, json5::Error> {
    let file: MetadataFile = json5::from_str(text)?;
    Ok(file
        .series
        .into_iter()
        .map(|(name, fields)| (name, fields.resolve(&file.defaults)))
        .collect())
}

/// Reads and parses the metadata file.
/// The error messages are shown to the user as-is, so they name the file involved.
pub fn load_metadata(path: &Path) -> Result<Catalog> {
    let text = fs::read_to_string(path).map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            anyhow!("Metadata file '{}' not found.", path.display())
        } else {
            anyhow::Error::new(error).context(format!("Failed to read '{}'", path.display()))
        }
    })?;
    parse_catalog(&text).with_context(|| format!("Failed to parse '{}'", path.display()))
}

/// Escapes `,` and `=` with a `^`, because ComicTagger uses them as delimiters in its `key=value,key=value` argument.
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

/// Builds the value for ComicTagger's `-m` option: a comma-separated list of `key=value` pairs.
/// For example (shortened):
/// ```text
/// manga=Yes,issue=-100000,black_and_white=Yes,language=en,...,volume=3,title=Volume 3,year=2021,credit=Writer:,credit=Writer:Jane Doe,characters=A^,B
/// ```
/// `volume` and `year` come from the filename (see the `filename` module); each is left out when `None`.
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

    // ComicTagger *adds* credits to the ones already stored in the file; it never replaces them.
    // Tagging a file that already has a writer would leave "Old Writer, New Writer".
    // A credit with an empty person is ComicTagger's way of saying "remove every existing credit for this role", so each role is cleared just before its real credit is added.
    // Roles this series does not list are left untouched.
    // Listing a role with an empty person therefore removes it.
    for (role, person) in &meta.credit {
        pairs.push(format!("credit={role}:"));
        if !person.is_empty() {
            pairs.push(format!("credit={role}:{}", escape(person)));
        }
    }

    // All characters go into a single `characters=` value.
    // Items are joined with an escaped comma (`^,`) so ComicTagger reads them as one list rather than as separate key=value pairs.
    // Note that a comma *inside* a name is escaped the same way, so it is indistinguishable from the separator (behavior carried over from the original script).
    if !meta.characters.is_empty() {
        let names: Vec<String> = meta.characters.iter().map(|name| escape(name)).collect();
        pairs.push(format!("characters={}", names.join("^,")));
    }

    pairs.join(",")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(text: &str) -> Catalog {
        parse_catalog(text).unwrap()
    }

    fn credit_of(series: &Series) -> Vec<(&str, &str)> {
        series
            .credit
            .iter()
            .map(|(role, person)| (role.as_str(), person.as_str()))
            .collect()
    }

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
             year=2021,credit=Writer:,credit=Writer:W,credit=Cover:,credit=Cover:C,characters=X^,Y"
        );
        assert!(!build_metadata_string(&meta, None, None).contains("volume="));
    }

    #[test]
    fn each_credit_role_is_cleared_before_it_is_added() {
        let meta = Series {
            credit: IndexMap::from([
                ("Writer".into(), "New, Writer".into()),
                ("Colorist".into(), "".into()),
            ]),
            ..Series::default()
        };
        let metadata = build_metadata_string(&meta, None, None);
        // Writer: a blank credit first (removes existing ones), then the real one.
        assert!(
            metadata.contains(",credit=Writer:,credit=Writer:New^, Writer,"),
            "{metadata}"
        );
        // Colorist has no person: only the clear is sent, which removes the role.
        assert!(metadata.ends_with(",credit=Colorist:"), "{metadata}");
        // A role the series doesn't list is never mentioned, so it is left alone.
        assert!(!metadata.contains("Letterer"), "{metadata}");
    }

    #[test]
    fn json5_features() {
        let catalog = parse(
            r#"
            // comment
            /* block */
            { Series: { 'Foo': {
                manga: true,
                characters: ['A', "B",],
                credit: { Writer: 'X', Cover: "Y", },
                unknown_field: 1,
            }, }, }
        "#,
        );
        let foo = &catalog["Foo"];
        assert!(foo.manga && !foo.black_and_white);
        assert_eq!(foo.characters, ["A", "B"]);
        // Credit order follows the file, not alphabetical order.
        assert_eq!(credit_of(foo), [("Writer", "X"), ("Cover", "Y")]);
    }

    #[test]
    fn old_manga_key_and_plain_json_still_work() {
        let catalog = parse(r#"{"Manga": {"X": {"manga": true}}}"#);
        assert!(catalog["X"].manga);
    }

    #[test]
    fn both_series_and_manga_keys_is_an_error() {
        assert!(parse_catalog(r#"{ Series: {}, Manga: {} }"#).is_err());
    }

    #[test]
    fn misspelled_top_level_key_is_an_error_not_silently_ignored() {
        let error = parse_catalog(r#"{ Defalts: { manga: true }, Series: {} }"#).unwrap_err();
        assert!(error.to_string().contains("Defalts"), "{error}");
    }

    #[test]
    fn defaults_fill_gaps_and_series_values_win() {
        let catalog = parse(
            r#"{
            Defaults: { manga: true, language: "en", maturity_rating: "Teen", publisher: "P" },
            Series: {
                Plain: {},
                Override: { manga: false, maturity_rating: "M" },
                Cleared: { publisher: "" },
            },
        }"#,
        );
        let plain = &catalog["Plain"];
        assert!(plain.manga);
        assert_eq!(plain.language, "en");
        assert_eq!(plain.maturity_rating, "Teen");

        let over = &catalog["Override"];
        assert!(!over.manga, "an explicit false must beat a default true");
        assert_eq!(over.maturity_rating, "M");
        assert_eq!(over.language, "en", "fields not overridden still inherit");

        assert_eq!(
            catalog["Cleared"].publisher, "",
            "explicit empty beats the default"
        );
        assert_eq!(plain.publisher, "P");
    }

    #[test]
    fn missing_defaults_block_behaves_like_before() {
        let catalog = parse(r#"{ Series: { X: {} } }"#);
        let x = &catalog["X"];
        assert!(!x.manga && !x.black_and_white);
        assert_eq!(x.language, "");
        assert!(x.credit.is_empty() && x.characters.is_empty());
    }

    #[test]
    fn credit_role_groups_expand_in_written_order() {
        let catalog = parse(
            r#"{ Series: { X: { credit: { "Cover, Inker ,Penciller": "Art", Writer: "Wri" } } } }"#,
        );
        assert_eq!(
            credit_of(&catalog["X"]),
            [
                ("Cover", "Art"),
                ("Inker", "Art"),
                ("Penciller", "Art"),
                ("Writer", "Wri")
            ]
        );
    }

    #[test]
    fn credit_merges_per_role_and_overridden_role_keeps_its_position() {
        let catalog = parse(
            r#"{
            Defaults: { credit: { "Cover, Letterer": "Studio" } },
            Series: { X: { credit: { Writer: "W", Cover: "Special" } } },
        }"#,
        );
        assert_eq!(
            credit_of(&catalog["X"]),
            [
                ("Cover", "Special"),
                ("Letterer", "Studio"),
                ("Writer", "W")
            ]
        );
    }

    #[test]
    fn characters_replace_rather_than_merge() {
        let catalog = parse(
            r#"{ Defaults: { characters: ["D"] }, Series: { A: {}, B: { characters: ["X"] } } }"#,
        );
        assert_eq!(catalog["A"].characters, ["D"]);
        assert_eq!(catalog["B"].characters, ["X"]);
    }

    #[test]
    fn empty_role_name_is_an_error() {
        for bad in [r#""Cover,": "A""#, r#""": "A""#, r#""Cover,,Inker": "A""#] {
            let text = format!("{{ Series: {{ X: {{ credit: {{ {bad} }} }} }} }}");
            let error = parse_catalog(&text).unwrap_err();
            assert!(
                error.to_string().contains("empty role name"),
                "{bad}: {error}"
            );
        }
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
        fs::write(&broken, "{ Series: { ").unwrap();
        let message = format!("{:#}", load_metadata(&broken).unwrap_err());
        assert!(message.starts_with(&format!("Failed to parse '{}': ", broken.display())));
    }
}