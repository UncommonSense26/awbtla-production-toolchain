# AWBTLA Production Toolchain

This toolchain typesets *A World Brought to Light Again* from its archival Markdown master into:
- one print interior PDF, used for both the paperback and the hardcover (7 × 10 in, no bleed);
- one reflowable EPUB 3 for Kindle.

It turns production into a single deterministic command. It is built to refuse to run rather than produce a wrong book.

**Do not use any pre-§58 manuscript file for production.** The prepublication master (SHA-256 52a781dd…) is *not* the production input. The only valid input is the release-verified master frozen in Continuity §58, identified by the hash recorded there.

## 1. Requirements

| Component | Version tested | Notes |
|---|---|---|
| Python | 3.12 | Needs PyYAML and pypdf (`pip install pyyaml pypdf`). |
| Pandoc | 3.1.3 | Needs Pandoc 3.x (`--split-level`). |
| LuaLaTeX | LuaHBTeX 1.17 (TeX Live 2023) | Needs luaotfload, fontspec, unicode-math, microtype, fancyhdr, tocloft, tabularx, needspace, ragged2e, enumitem, emptypage, hyperref. On Debian/Ubuntu install texlive-luatex, texlive-latex-extra and texlive-fonts-recommended. Without texlive-luatex, LuaLaTeX cannot load any OpenType font. |
| Poppler | pdftotext, pdffonts | Used by the QA scripts. |
| Java | 11 or later (tested with 21) | Runs EPUBCheck. |
| Fonts | Source Serif 4 4.005R; STIX Two Math 2.13 | Pinned by SHA-256 in deps.lock.json and vendored in vendor/fonts under the SIL Open Font License. |
| EPUBCheck | 5.1.0 | Installed by install_dependencies.py. |

Run once per machine:

```
python3 install_dependencies.py
```

It downloads anything missing and verifies every font file and the EPUBCheck archive against deps.lock.json. It exits non-zero on any mismatch.

## 2. Layout

| Path | Contents |
|---|---|
| build.py | The single entry point: gates, build, calibration ladder, QA, manifest. |
| preprocess.py | Converts archival structure into Pandoc Markdown. It changes markup only and never text. It also breaks long display equations into aligned lines. |
| filters/awbtla.lua | Structural rendering in three modes: print (LaTeX), EPUB, and plain text for QA. |
| templates/awbtla-template.tex | Page architecture, typography, running heads, notes, formula guard, signature table. |
| epub/awbtla-epub.css | EPUB styling. |
| qa/ | qa_structure.py (source), qa_pdf.py (layout), qa_text.py (content integrity), qa_epub.py (EPUBCheck, navigation, accessibility, links). |
| manifest.py | Writes the JSON and Markdown manifests. |
| production_config.yaml | Print parameters, calibration ladder, page limits, running-head map, and the expected chapter titles that guard the map. |
| publication_metadata.template.yaml | Copy it, fill it in after the ISBN and imprint evidence is resolved, and pass it with `--metadata`. |
| tests/ | The synthetic fixture, and run_tests.py (positive build, reproducibility, negative tests). |
| vendor/ | Pinned fonts and EPUBCheck. |

## 3. Final production invocation

```
python3 build.py \
  --input AWBTLA_RELEASE_VERIFIED_MASTER_YYYY-MM-DD.md \
  --expected-sha256 <HASH_FROM_SECTION_58> \
  --metadata publication_metadata.yaml \
  --config production_config.yaml \
  --formats paperback hardcover epub \
  --outdir AWBTLA_PRODUCTION_BUILD_YYYY-MM-DD \
  --authorize-production
```

No default ever selects a manuscript. `--input`, `--expected-sha256` and `--metadata` are always required.

## 4. Fail-closed behavior

The build runs these checks in order and stops at the first failure. Nothing is created before step 6.

| Step | Stops with exit code when |
|---|---|
| 1. Input | the file is missing (2). |
| 2. Hash gate | the computed SHA-256 differs from `--expected-sha256` (3). |
| 3. Mode | a synthetic fixture is used without `--synthetic-test`, or a real file with it (11). |
| 4. Authorization gate | `--authorize-production` is absent. The build prints the validation results and stops (4). |
| 5. Metadata and structure | any required value is missing or a placeholder, `copyright_year` differs from the publication year, an ISBN fails its checksum, or the source structure QA fails (5 or 7). |
| 6. Fonts | a production font is missing or fails its hash (6). There is no silent substitution: fallback fonts exist only in `--synthetic-test` mode with `--allow-fallback-fonts`, and those outputs are labelled on the title and copyright pages. |

Metadata checks in step 5:
- Placeholders are rejected: TBD, UNKNOWN, TODO, PLACEHOLDER, XXXX, or any bracketed value such as `[ISBN]` or `[DATE]`.
- Title, author, edition and language must match exactly.

Only after step 6 is the output directory created. If an existing output directory is not empty, the build refuses to use it.

## 5. What the print build does

**Front matter:** half-title, blank verso, title page, copyright page generated from the metadata, then Contents.
- The copyright page has no special Petition-reproduction license.
- Front matter is numbered in lowercase roman. The half-title, title and copyright pages print no folio.

**Numbering:** arabic page 1 is the first page of the Legal Notice.

**Openings:**
- These start on a recto: Legal Notice, Preface, Prologue, Introduction, each Part, Constitution, People's Petition, Endnotes, Dedication.
- Chapters start on the next page, whichever side it is.
- The Index of Formal Models starts on the next page.
- Part pages are rectos with no head or folio, followed by a blank verso.
- Blank pages carry nothing.

**Running heads:**
- The verso shows the Part title, or the name of the special section.
- The recto shows "Chapter N: Short Title", "Constitution: Article N", "People's Petition", "Index of Formal Models" or "Endnotes".
- Opening pages have no running head and a centered folio. Other folios sit at the bottom outside.
- Short titles come from the configuration, never from edits to the manuscript. The build stops if a chapter title no longer matches `expected_chapter_titles`.
- The typesetter measures every head and flags any wider than the measure.

**Type:**
- Source Serif 4 at 10.75/14 pt; endnotes 8.75/11.25 pt; formal-model keys and prompts 10/13 pt; mathematics in STIX Two Math.
- Justified, with a 1.5 em first-line indent and no paragraph spacing.
- No indent after headings, scene breaks, formal-model blocks or lists.

**Hyphenation:**
- At least 3 characters before and after any break.
- Consecutive hyphenated lines and hyphens across a page break are strongly discouraged.
- Microtype protrusion and ±2% font expansion.
- No hyphenation in headings, Contents entries, running heads, capitalized words, or protected identifiers:
  - hyphenated tokens containing digits are wrapped in `\mbox`;
  - URLs and DOIs use `\url` and break only at `/` or `.`;
  - ties are placed after §, "No." and reporter abbreviations.
- Protection exists only in the generated TeX; the archival Markdown is never changed.

**Page breaks:**
- Widow and club penalties are 10000.
- Headings keep with the following text.
- Formal-model blocks (label, display, Where:, Common Sense Prompt:) are set as one unbreakable unit.

**Formulas:**
- Long displays are broken before top-level arrows and relations into aligned lines, and `\qquad`-separated relations are stacked.
- The template then measures every display. It scales down only if the result stays at 90% or more; beyond that it reports AWB-FORMULA-OVERFLOW, which fails QA.
- No formula is ever rasterized.

**Constitution and Petition:** the text and hierarchy are exact.
- Article headings are set as label and title on stacked lines; no colon is added.
- Section paragraphs are unchanged.
- The Petition signature table keeps its header wording verbatim, fits the measure in portrait, and has ruled rows 0.33 in high.

**Endnotes:**
- Global numbers are preserved, never renumbered.
- Each note has a hanging indent and is set ragged right.
- Links run from the body marker to the note, and from the note number back to the marker.

**PDF:**
- Title, author, and language en-US are set.
- Bookmarks are nested:
  - Parts contain their chapters;
  - the Constitution contains the Preamble and Articles;
  - there is no flat list.
- Fonts are embedded, and extraction is ligature-safe.
- The PDF is **not tagged**. The LaTeX tagging code in TeX Live 2023 is experimental and is not used, to protect layout and extraction.

**Calibration ladder:**
1. First build at 10.75/14.
2. Above 540 pages: 10.5/13.75 with notes at 8.5/11.
3. Above 548 pages: outside margin 0.5 in, top and bottom 0.7 in.
4. Above 550 pages: STOP with "HARDCOVER TRIM SPLIT REQUIRED UNDER PRODUCTION DECISION RECORD", and the oversized PDF is deleted.

Manuscript text is never cut to meet a page count.

## 6. EPUB

- Reflowable EPUB 3 with a nav document: Parts at level 1 with their chapters nested at level 2, specials at level 1.
- Section subheadings, Articles and endnote groups are kept out of the navigation, matching Contents.
- Linked endnotes with back-links.
- Mathematics in MathML.
- Source Serif 4 embedded (the SIL Open Font License permits this).
- Language en-US, and accessibility metadata: accessMode, accessModeSufficient, accessibilityFeature, accessibilityHazard, accessibilitySummary.
- Deterministic zip packaging.
- Must pass EPUBCheck 5.1.0.

## 7. QA (all automatic; any failure stops the build and suffixes the artifact with .QA-FAILED)

**Structure (source):**
- Every note marker resolves, with no orphans and numbering 1..N in first-appearance order.
- Every internal "global note" reference resolves.
- Every model in the Index has a labelled block, and all required models are present.
- The Legal Notice, Constitution, Petition, Index, Endnotes and Dedication regions exist.
- Title and author are exact.
- Counts are read from the source, never assumed.

**Layout (PDF):**
- Exact 7 × 10 page boxes.
- No text outside the measure, beyond a 3 pt allowance for margin protrusion; no clipping; nothing outside the 0.25 in safe zone.
- No running-head overflow, and no formula-overflow markers.
- No overfull lines wider than 1 pt, and no missing glyphs.
- No replacement characters, and no ligature code points in the extracted text.
- Em dashes equal the source count.
- No folio on a blank page; no duplicate folios; every printed folio matches its page label.
- No heading in the last two lines of a full page, and no split formal-model blocks.
- All fonts embedded, and the production fonts present.

**Content integrity:**
- Source text (Pandoc plain rendering) is compared token by token with text extracted from the PDF and from the EPUB.
- It detects missing, extra, changed and reordered text, missing or extra note markers, and dropped headings.
- Allowed normalizations only:
  - whitespace and line wrapping;
  - running heads and folios, excluded by page geometry;
  - ligature letters;
  - end-of-line hyphenation and URL/DOI breaks, joined only when the joined form exists in the source;
  - wildcards for mathematics, fill-in blank rules, and the signature table.
- Punctuation is never normalized.

**EPUB:**
- EPUBCheck.
- dc:language en-US.
- Accessibility metadata.
- Every note link and back-link resolves.
- Em-dash count.
- Content integrity, as above.

## 8. Outputs

- `AWBTLA_PRINT_INTERIOR_7x10_<publication date>.pdf`: the interior for both the paperback and the hardcover.
- `AWBTLA_EBOOK_<publication date>.epub`.
- `AWBTLA_PRODUCTION_MANIFEST.json` and `.md`, recording:
  - the build time;
  - the source file and its computed and expected hashes;
  - the configuration, metadata and toolchain hashes;
  - Pandoc and LuaLaTeX versions, and fonts with their versions;
  - trim, type size and leading, calibration level, and page count;
  - ISBNs and publication date;
  - every output with its SHA-256;
  - all QA results;
  - cover parameters. The paperback spine estimate is pages × 0.0025 in on cream paper. The hardcover wrap comes from the platform calculator.

Cover artwork and wraps are never generated here.

## 9. Synthetic testing

```
python3 tests/run_tests.py          # results in tests/test_runs/results.json; build outputs removed
python3 tests/run_tests.py --keep   # keep the synthetic build directories for inspection
```

The fixture holds only generic structural text and carries the marker `<!-- AWBTLA-SYNTHETIC-FIXTURE -->`. Synthetic outputs are prefixed SYNTHETIC_TEST_ and labelled on the title and copyright pages.

## 10. Reproducibility

- `SOURCE_DATE_EPOCH` is set from the publication date, with `FORCE_SOURCE_DATE=1`.
- The PDF trailer ID and PTEX info are suppressed.
- The EPUB zip is written with fixed timestamps and order.
- The synthetic test builds twice and compares the SHA-256 of the outputs; the result is recorded in results.json and the build report.
- The manifest field `toolchain_sha256` is computed over the explicit `TOOLCHAIN_FILES` list in build.py (path plus file hash), so output folders, caches, and a local publication_metadata.yaml never change it.

## 11. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "metric data not found or bad" / "luaotfload-main not found" | texlive-luatex is not installed. |
| Exit 3 | The input is not the §58 master. Do not edit the file to force a match. |
| Exit 4 | This is expected until the author authorizes production. |
| Exit 5 | Fill publication_metadata.yaml from verified ISBN, imprint and date evidence. |
| Exit 6 | Run install_dependencies.py. |
| Exit 7 | The source structure changed, for example a chapter title differs from `expected_chapter_titles`. Update the configuration's running-head map only if the title change is part of the §58 master. |
| Exit 8 | Stop and apply the hardcover trim fallback under the decision record. |
| Exit 9 or 10 | Read `qa` in the manifest. Fix the toolchain or configuration, never the manuscript text. |
