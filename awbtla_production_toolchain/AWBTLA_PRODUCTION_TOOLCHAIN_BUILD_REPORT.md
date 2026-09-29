# AWBTLA Production Toolchain Build Report

Date: September 29, 2026. Scope: production toolchain engineering only. The toolchain was run only on a synthetic fixture. No manuscript text was edited, no PDF, DOCX, EPUB, cover, print file, or distribution package was generated from the manuscript, RD-01 to RD-08 were not rerun, §58 was not created, KDP was not touched, and this is not Pass 11.

## I. Controlling state

All nine controlling hashes were verified before work began and again after it ended. They were unchanged.

| File | SHA-256 |
|---|---|
| AWBTLA_PREPUBLICATION_VERIFIED_FINAL_MASTER.md | 52a781dd5042b2e2b84166387028e0f74589b32043245fd57d452c314552da19 |
| AWBTLA_REOPEN_PASS3_CONTINUITY.md (through §57) | 933151b8113c46620f9f10b6fdb3dfb905d899896cf5d525dbc6f9ab397382dd |
| AWBTLA_FINAL_PRODUCTION_READINESS_PACKET.md | 76b9b101bba2ae426d049e7bc285eacab162242afcbd51641d014fb738488912 |
| AWBTLA_FROZEN_PROJECT_ARCHIVE_INDEX.md | 3eae521c8af6ccf28873260bb83cacce094de754fe46d3d7ea246b6de9312cd5 |
| AWBTLA_RELEASE_CHECK_INTERIM_STATUS_2026-09-29.md | f941ac6f37da84182835e8f086c4a19c5d37f492bfe82f28c9bb59e0d36f8efd |
| AWBTLA_FINAL_PRODUCTION_SPECIFICATION.md | 20e756010a219b156d45d29e1485892ca83eac3cb21f65c647a90fdf720eb30b |
| AWBTLA_PRODUCTION_PARAMETER_DECISION_RECORD.md | baa57bb14734afeb4bc651ba084054c74fd84d43ff6b50a740d4be67a4a283e8 |
| AWBTLA_ISBN_COVER_METADATA_RESOLUTION.md | 8093df3248fe29951db6a2d960be274a68cca4e41ca7e1cb6eacb6fc8d09d678 |
| AWBTLA_PRODUCTION_CONTROL_ADDENDUM.md | aca5acb3da1a4c7a06f1d70ba0c11f6ab40a7f1b110efd9505533ee046016f37 |

The toolchain implements the configuration in section IX of the Production Control Addendum. The current prepublication master is not the production input. The build accepts only a file whose SHA-256 is supplied explicitly, and that value is to come from Continuity §58.

## II. Files created

The directory awbtla_production_toolchain/ holds 38 files, listed with hashes in section XIV. It is separate from pass10_state/, which was not touched, and it contains no hard-coded /home/claude/p10/ path.

- Entry point and pipeline: build.py, preprocess.py, filters/awbtla.lua, templates/awbtla-template.tex, epub/awbtla-epub.css, manifest.py.
- QA: qa/qa_structure.py, qa/qa_pdf.py, qa/qa_text.py, qa/qa_epub.py.
- Configuration: production_config.yaml (the full production parameter set, the running-head map for Chapters 1 to 30, and the expected chapter titles that guard that map) and publication_metadata.template.yaml.
- Dependencies: deps.lock.json (pinned URLs and SHA-256 values) and install_dependencies.py.
- Fonts: vendor/fonts/, holding Source Serif 4 version 4.005R (13 OTF files) and STIX Two Math version 2.13, both under the SIL Open Font License, with their license texts.
- vendor/epubcheck/README.txt. EPUBCheck 5.1.0 itself (about 32 MB) is installed and hash-verified by the installer, not shipped.
- Tests: tests/fixture/ (a synthetic master, configuration, and metadata), tests/run_tests.py, and tests/test_runs/results.json (the recorded results; the build outputs were deleted after recording).
- README.md.

## III. Architecture

The command runs in this order: hash gate, mode check, metadata and source-structure validation, authorization gate, font gate, and only then creation of the output directory.

1. **Structure conversion.** preprocess.py reads the master and emits an intermediate Pandoc Markdown in which only structural markup changes:
   - headings carry classes and attributes;
   - `[^n]` becomes `[n]{.awb-ref}`;
   - endnote entries become note divs;
   - display equations are re-broken into aligned lines.
   The archival master is never written.
2. **Print.** One Lua filter serves three modes. In print mode it feeds a LuaLaTeX template, which Pandoc converts to TeX and LuaLaTeX runs three times.
3. **EPUB.** In EPUB mode the same filter feeds Pandoc's EPUB 3 writer, followed by accessibility post-processing and EPUBCheck.
4. **QA text.** In plain mode it renders the reference text used by the text-integrity check.
5. **Page count.** The calibration ladder rebuilds at the second and third configurations as needed.
6. **Record.** Every authorized build writes AWBTLA_PRODUCTION_MANIFEST.json and AWBTLA_PRODUCTION_MANIFEST.md.

## IV. Hash gate

`--input` and `--expected-sha256` are both required. No default selects a manuscript.

The build checks that the file exists, computes its SHA-256 itself, and compares that to the supplied value. On a mismatch it exits with code 3 before any directory or file is created. On a match it logs the verified hash.

A mode check also runs. A file carrying the synthetic-fixture marker is refused for production, and `--synthetic-test` refuses a file without the marker.

Tested: a wrong hash exits 3, and no output directory is created.

## V. Authorization gate

Without `--authorize-production`, the build validates and then stops with exit 4 and the message "PRODUCTION IS NOT AUTHORIZED: no artifacts were created."

With the flag set, the build also enforces these checks:
- **Metadata.** Every required field must be real, not a placeholder (TBD, UNKNOWN, TODO, XXXX, or any [BRACKETED] value).
- **Identity.** Title, author, and edition must match exactly, and language must be en-US.
- **ISBNs.** Each ISBN-13 must pass its checksum, and each format needs its own ISBN.
- **Dates.** The publication date must be a valid ISO date, and the copyright year must equal the year of first publication.
- **Structure.** Source-structure QA must pass.

A font gate follows. The pinned production fonts must be present and must match their SHA-256 values, or the build stops with exit 6. Fallback fonts are possible only with both `--synthetic-test` and `--allow-fallback-fonts`, and they are then labelled on the title and copyright pages and in the manifest.

Tested: a missing flag exits 4 with no output directory, a placeholder ISBN exits 5, and an empty font directory exits 6.

## VI. PDF pipeline

**Trim and fonts**
- 7 × 10 in with no bleed.
- Mirrored margins: inside 0.875, outside 0.625, top 0.75, bottom 0.75 in.
- Source Serif 4 through fontspec: Text for the body, SmText for notes and furniture, Display for titles. STIX Two Math through unicode-math.
- Body 10.75/14 pt, endnotes 8.75/11.25 pt, formal-model keys and prompts 10/13 pt.

**Paragraphs**
- Justified, with a 1.5 em first-line indent and no paragraph spacing.
- No indent after headings, scene breaks, formal-model blocks, or lists.

**Title matter**
- Half-title, blank verso, title page (no subtitle), copyright page, then Contents.
- Half-title and title page print no folio; front matter uses lowercase roman; arabic 1 begins on the Legal Notice.
- The copyright page is generated from the metadata. It carries the title, "Copyright © [year] Justin Andre Lamoureux", all-rights-reserved language with the ordinary exceptions for quotation in reviews, scholarship, criticism, and commentary, the publisher line, First Edition, ISBN lines by format, and a one-sentence pointer to the Legal Notice. It carries no Petition-reproduction permission.

**Openings**
- On a recto: Legal Notice, Preface, Prologue, Introduction, each Part, Constitution, People's Petition, Endnotes, and Dedication.
- On the next page: Chapters 1 to 30 and the Index of Formal Models.
- Part pages carry the label and title only, with no head or folio, followed by a blank verso.
- Blank pages carry no head or folio. The Dedication carries neither.

**Running heads**
- Verso: the Part title, or the name of the special section.
- Recto: "Chapter N: Short Title", "Constitution: Article N", "People's Petition", "Index of Formal Models", or "Endnotes".
- Opening pages have no head; their folio is centered at the bottom. Other folios sit at the bottom outside.
- The map lives in production_config.yaml, not in the manuscript. A stale map fails the build, because each chapter's expected title is checked against the source.
- The typesetter measures every head and logs AWB-HEAD-OVERFLOW if one is too wide.
- All 48 configured production heads were measured in the production head font. The widest, Chapter 5, is 262.5 pt against a 397.5 pt measure.

**Hyphenation and page breaks**
- Minimum 3 letters before and after a break.
- Hyphen penalty 700; demerits of 900,000 for consecutive hyphenated lines and for a hyphenated final line.
- `\brokenpenalty=10000`, so no hyphen at a page turn; `\uchyph=0`, so no capitalized or all-capital word is hyphenated.
- Headings, Contents entries, and running heads are set with hyphenation disabled.
- Microtype protrusion with ±2% expansion.
- Widow, club, and display-widow penalties of 10,000.
- Headings reserve 5 to 6 lines with needspace, so no heading lands in the last two lines of a page. Formal-model blocks are unbreakable boxes.

**Formal models**
- The label, displays, "Where:" key, and "Common Sense Prompt:" are grouped into one block.
- Long displays are broken before arrows and relations at the top level, with aligned continuation lines, and separate relations are stacked.
- The typesetter measures every display. It scales one only when it fits at 90% or more; otherwise it logs AWB-FORMULA-OVERFLOW and QA fails.
- Mathematics stays as vector text in STIX Two Math, with italic variables and attached subscripts. Nothing is rasterized.

**Constitution**
- The title line, PREAMBLE, and each ARTICLE label and title are kept exactly as in the source.
- The label and title stack on two lines with no added colon. This intentionally departs from the September proof's merged "ARTICLE N: TITLE" treatment.
- Sections stay as run-in paragraphs with no numbering or emphasis added.
- Article headings keep with the following text.

**People's Petition**
- Title, subtitle, and Articles are exact.
- The signature table uses the source's column wording verbatim, 7.5 pt headers, ruled rows 0.33 in high, and fits the portrait measure. No landscape page was needed.
- Fill-in underscore runs print as rules of proportional length.

**Index and endnotes**
- The Index of Formal Models is a hanging-indent list.
- Endnotes keep the master's global numbers, with no renumbering. Section subheads are kept.
- Notes use a hanging indent, 8.75/11.25 pt, and ragged right.
- Links run both ways: marker to note and note back to marker.

**Identifier protection**
- Applied in the generated TeX only.
- Any token combining digits and hyphens (case, docket, report, and FCC or Federal Register document numbers, ISBNs, hyphenated dates) is boxed.
- URLs and DOIs are set with `\url`, which breaks only at slashes and dots, never at hyphens.
- A nonbreaking space is used after §, No., amend., and similar abbreviations, and around reporter abbreviations (U.S., U.S.C., F.3d, So. 3d, Fed. Reg., FCC Rcd).

**PDF metadata and accessibility**
- Title, author, and `/Lang en-US` are set, and the PDF opens with bookmarks shown.
- Bookmarks are nested: Parts contain their Chapters, and the Constitution contains its Preamble and Articles.
- All fonts are embedded, and the extracted text contains no ligature code points.
- Internal links are real link annotations.
- The PDF is not tagged. LaTeX's tagging code in TeX Live 2023 is experimental and could damage layout or extraction, so it is not used.

## VII. EPUB pipeline

- Pandoc builds a reflowable EPUB 3 with no pagination, running heads, or folios.
- Headings are semantic, with Parts at level 1 and Chapters at level 2.
- The navigation document is nested, with Chapters under their Parts. Constitution Articles and inner subheadings are excluded so the navigation matches the printed Contents.
- Notes link both ways, using doc-noteref and doc-backlink roles.
- Mathematics is in MathML.
- Language is en-US.
- Accessibility metadata is present: accessMode, accessModeSufficient, accessibilityFeature, accessibilityHazard, and accessibilitySummary.
- Source Serif 4 is embedded, which the Open Font License permits.
- The package is re-zipped deterministically, with the mimetype file first and stored uncompressed.
- EPUBCheck 5.1.0 is run automatically and fails the build on any fatal error or error.

## VIII. QA architecture

Any QA failure stops the build with a non-zero exit, suffixes the artifact with .QA-FAILED, and records the details in the manifest.

**Structure (source, read-only)**
- Endnote entries run 1 to N, and markers appear once each in first-appearance order.
- There are no orphan notes and no unresolved markers, and all "global note" cross-references resolve.
- Every model in the Index has a labelled block, and all 17 required models (TM-01 to TM-17) are present.
- The Legal Notice, Constitution, Petition, Index, Endnotes, and Dedication all exist.
- Source title and author match the metadata.
- Counts are read from the source. An optional expected_note_count is compared only if §58 supplies one.

**Layout (PDF)**
- Every page box is exactly 7 × 10 in.
- No word sits outside the mirrored text measure or outside the 0.25 in safe zone, and no text is clipped.
- No running head overflows, and no AWB-HEAD-OVERFLOW or AWB-FORMULA-OVERFLOW marker appears in the log.
- No overfull line is wider than 1 pt, and no glyph is missing.
- There are no U+FFFD replacement characters and no ligature code points in the extracted text.
- The em-dash count equals the source count (the baseline has no authorial em dashes).
- No blank page carries a folio.
- Each printed folio matches its page label, and no folio is duplicated.
- No heading sits in the last two lines of a page, and no formal-model block splits across pages.
- There are no runs of three or more hyphenated lines and no hyphen at a page turn.
- Widows and orphans are detected by geometric heuristics.
- All fonts are embedded, and Source Serif 4 and STIX Two Math are present.

**Text integrity**
- The reference text is Pandoc's plain rendering of the intermediate Markdown. It is compared token by token, with resynchronization, against text extracted from the PDF (from arabic page 1) and from the EPUB spine.
- The check reports missing, extra, changed, and reordered text, missing or extra note markers, and dropped headings.
- Only these normalizations are allowed: whitespace and line wrapping; running heads and folios; the five ligature characters; end-of-line hyphenation, joined only when the joined word exists in the source vocabulary; and wildcard tokens for mathematics and the signature table, which are checked separately.
- Punctuation is never normalized.

**EPUB**
- EPUBCheck, language, accessibility metadata, resolution of every note link and back-link, the em-dash count, and text integrity.

## IX. Synthetic test results

Fixture: tests/fixture/synthetic_master.md, SHA-256 45032d23f030ad37a6e5ef8bf6959340352bfb4fd9eea1c702202ab0215ef15c. It contains only generic structural labels and filler text:
- two Parts and two Chapters, one with a deliberately long heading;
- legal-style identifiers, a DOI, and a URL;
- a formal model with a chain long enough to need breaking;
- a two-Article Constitution;
- a Petition with a 10-row signature table;
- four endnotes, one internal cross-reference, and a Dedication.

The positive build ran with production fonts, not fallbacks, and exited 0 at 43 pages.

**Structure and navigation**
- Every required opening fell on a recto (Legal Notice, Preface, Prologue, Introduction, Part I, Part II, Constitution, Petition, Endnotes, Dedication).
- Arabic page 1 is the Legal Notice.
- Bookmarks are nested, with Chapters under Parts and the Preamble and Articles under the Constitution.
- Destinations note-1 to note-4 and ref-1 to ref-4 exist, with 13 internal link annotations. `/Lang` is en-US and the title and author are set.

**Running heads and formulas**
- Running heads appear as configured ("Part II: Synthetic Part Two", "Chapter 2: Second Synthetic Chapter", "Constitution of the World Peoples Union", "Constitution: Article II", "People's Petition").
- The long display broke into three lines, with zero formula-overflow and zero head-overflow markers.

**Tables and EPUB**
- The signature table has 10 ruled rows and verbatim headers.
- EPUBCheck reported 0 fatal errors, 0 errors, and 0 warnings. The navigation nests Chapters under Parts, and MathML is present.

**QA**
- Print layout QA: 0 failures.
- Print text integrity: passed, with 6,056 source tokens.
- EPUB text integrity: passed.

A contact sheet of ten representative pages was inspected visually: copyright page, Contents, Legal Notice opening, Part page, chapter opening with the model block, a verso text page, Constitution opening, signature page, Endnotes, and Dedication.

**Reproducibility**: two builds from identical inputs were byte-identical.
- PDF: baf2c31b83e672fbe61ab8c4c62d2e29172076253cfb7d1b95c46788a4cd42ac, both times.
- EPUB: b302443053ace114b4f4146261c1858e07b94fcfb4cbc6f970cdf65dea62be0f, both times.
- This rests on SOURCE_DATE_EPOCH set from the publication date, FORCE_SOURCE_DATE, a suppressed PDF ID and PTEX information, and a fixed-timestamp EPUB zip.
- It is demonstrated only for this environment. Different software versions will change the bytes.

The synthetic outputs were deleted after the results were recorded in tests/test_runs/results.json.

## X. Negative test results

| Test | Expected | Result |
|---|---|---|
| Wrong source hash | Exit 3 before anything is created | Exit 3; no output directory. PASS |
| Missing authorization flag | Exit 4 before anything is created | Exit 4; "PRODUCTION IS NOT AUTHORIZED"; no output directory. PASS |
| Placeholder ISBN "[PAPERBACK ISBN]" | Exit 5 in authorized mode | Exit 5; no output directory. PASS |
| Missing production font (empty font directory) | Exit 6 in authorized mode | Exit 6; no output directory. PASS |
| Oversized page count (limits lowered to 5, 6, and 7) | Ladder, then stop | Built at target, second, and third configurations, then exit 8 "HARDCOVER TRIM SPLIT REQUIRED UNDER PRODUCTION DECISION RECORD"; oversized PDF deleted. PASS |
| Formula overflow (unbreakable display) | QA failure | Exit 9; AWB-FORMULA-OVERFLOW plus content outside the measure. PASS |
| Running-head overflow (over-long configured head) | QA failure | Exit 9; AWB-HEAD-OVERFLOW plus head outside the measure. PASS |
| Text mismatch (one word tampered in the reference text) | QA failure | Tampered reference failed ("changed: precedes/follows"); true reference passed. PASS |
| Missing note (entry 4 deleted) | QA failure | Exit 7, "markers without entries: [4]". PASS |

All nine negative tests passed on the final code.

## XI. Dependencies still unavailable

None in the build environment used here.

The production machine needs:
- Python 3 with PyYAML and pypdf;
- Pandoc (3.1.3 tested);
- TeX Live with LuaLaTeX (2023 tested) and fontspec, unicode-math, microtype, fancyhdr, emptypage, tocloft, needspace, ragged2e, mathtools, enumitem, tabularx, and hyperref;
- poppler-utils (pdftotext and pdffonts);
- Java for EPUBCheck.

`python3 install_dependencies.py` downloads and verifies the pinned fonts and EPUBCheck.

Kindle Previewer was not available, so Kindle rendering of MathML is unverified. That check belongs to the platform recheck at final setup.

## XII. Known limitations

1. **Not run on the manuscript.** As instructed, the toolchain was never run on the manuscript. The parser was written against the master's markup, inspected read-only. Unknown headings, stale chapter titles, or a missing required region stop the build at the first authorized run, but actual page count, build time, and the behavior of all 23 real displays are untested until then.
2. **Formula breaking is heuristic.** Breaking uses an estimated width limit (formula_break_chars: 60). Any display that still overflows after scaling to 90% fails QA. The remedy is to adjust that setting, never to change the formula.
3. **Some checks are heuristic.** Widow and orphan detection, and the maximum of two consecutive hyphenated lines, are enforced by engine penalties and then by geometric checks on the PDF. Those checks fail the build but could miss an unusual case.
4. **Untagged PDF.** The PDF is untagged (section VI).
5. **MathML only.** The EPUB uses MathML. An accessible SVG fallback is not implemented.
6. **Constitution heads.** Recto heads in the Constitution show the first Article whose heading appears on that page, which is the LaTeX default.
7. **Manuscript finding (not edited).** The endnote section headings for six chapters do not match the chapter titles. The toolchain prints the headings as they are and takes running heads from the chapter titles. Whether to align them is an author decision. Under current change control it cannot happen without an express direction.

| Chapter | Chapter title | Endnote heading |
|---|---|---|
| 15 | CONSTITUTIONAL FLOOR | The Constitutional Floor |
| 19 | LAW WITHOUT A PERMANENT LEGISLATURE | Lawmaking Without a Legislature |
| 20 | ADMINISTRATION WITHOUT A SOVEREIGN EXECUTIVE | Administration Without an Executive |
| 21 | JUSTICE, PETITIONS, AND REMEDIES | Justice |
| 22 | AI WITHOUT SOVEREIGNTY | Constitutional Artificial Intelligence |
| 23 | PRODUCTION, CHOICE, AND INNOVATION | Production and Productive Resources |

## XIII. Exact future production command template

Run after §58 records the release-verified master and its hash, and after ISBN and imprint evidence is resolved and publication_metadata.yaml is completed from the template:

```
python3 install_dependencies.py
python3 build.py \
  --input AWBTLA_RELEASE_VERIFIED_MASTER_YYYY-MM-DD.md \
  --expected-sha256 <HASH_FROM_SECTION_58> \
  --metadata publication_metadata.yaml \
  --config production_config.yaml \
  --formats paperback hardcover epub \
  --outdir AWBTLA_PRODUCTION_BUILD_YYYY-MM-DD \
  --authorize-production
```

Running the same command without `--authorize-production` performs a validation-only dry run that creates nothing.

Outputs:
- AWBTLA_PRINT_INTERIOR_7x10_<publication date>.pdf, one interior for both the paperback and the hardcover;
- AWBTLA_EBOOK_<publication date>.epub;
- AWBTLA_PRODUCTION_MANIFEST.json and AWBTLA_PRODUCTION_MANIFEST.md, which record the source and expected hashes, config and metadata hashes, toolchain hash, tool versions, fonts, trim, sizes, calibration level, page count, ISBNs, publication date, output hashes, all QA results, and cover parameters.

The cover parameters are only an estimate of the paperback spine (0.0025 in per cream page) plus a pointer to the hardcover calculator. No cover or wrap is generated.

## XIV. Toolchain hashes

- toolchain_sha256, the value each manifest will record: 10c66bf652967b3884b22689c31d262d246aee80cd5bc9eadcb2d857e01e3bb1. It is computed over the 20 source, configuration, and test files in build.py's TOOLCHAIN_FILES list.
- Directory hash: 8575730dcba55d7ed0168884dbac43f2ba6d0b635587c78ca8b0c6f4342b865d. This is the SHA-256 of the sorted `sha256sum` listing of all 38 delivered files.

| File | Bytes | SHA-256 |
|---|---|---|
| README.md | 13811 | 052accb72c87b63a577e5d678540e86d5cd5b4edd3bcbed1652814e58758e2ed |
| build.py | 21845 | 3c61963e37c9157d1c411eb7594e9aca1484f9b2604de6c5f1cc28dcdf682ce1 |
| deps.lock.json | 2418 | fb6227c7ee16499d4d52a1f2d718b8fd7175bf17a211c1af7697f6c941adf3d5 |
| epub/awbtla-epub.css | 1612 | aabe6a417ae7451376441f3971585b663bc9a519f4a59a9f5d29af32c9a010a9 |
| filters/awbtla.lua | 11021 | 99c26c04e62f451ee7a2d212e5ec846ad285d348ea0cce6d340be612f656ad35 |
| install_dependencies.py | 2259 | ec847ea8dbd42e1b653bc7046148490f365d8a8aad092e65acf626a5a203b067 |
| manifest.py | 1429 | bf5022450e7be19661e9c386500fdcf4931fdc242e441da8a3e95d96e6c5474d |
| preprocess.py | 13155 | 02fe7a71538093a8c21a42ef5e8ec49b2c667ade02ff7f02b02eda70390df151 |
| production_config.yaml | 4019 | 7242d2a7ba33691842cb5191256f38bf28185c7e4ddb75a03581347422c8c78c |
| publication_metadata.template.yaml | 791 | 5d1b7e3ac01bea08ff06a8760468b7fc6bd275e95542c98dfed5113514f65820 |
| qa/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| qa/qa_epub.py | 3508 | 3ebbbeb861a0365dffc8423a42ff3d7e244707ea723bd7dc597a777340da0060 |
| qa/qa_pdf.py | 8714 | 13cbe4a14b73b98aec228724ada63a36449c4110361432bedc4f2aea70155c66 |
| qa/qa_structure.py | 2543 | e1a1770d12cc013f41a7d9e81c9662a614a7b6c0d96e2b482e55f84ec54fb90e |
| qa/qa_text.py | 3951 | c3f797afc0b6f18d10f11b1afa5261610ea8a11e0c46d59512d899e0e4111775 |
| templates/awbtla-template.tex | 10236 | acbfcc9e9cac25b1ee0db1d56caa5dc9616c00f2f3a95a3dbd1099caba753c30 |
| tests/fixture/synthetic_config.yaml | 1428 | ebeed7b791c33dc3470bd3c9f1e3285a4f06fd19b2b53caa2ef1ab58e637409e |
| tests/fixture/synthetic_master.md | 48310 | 45032d23f030ad37a6e5ef8bf6959340352bfb4fd9eea1c702202ab0215ef15c |
| tests/fixture/synthetic_metadata.yaml | 460 | 510f900af6792b019879bb6e1140dba4ab39bd42b31f220c5f102db1a091fc20 |
| tests/run_tests.py | 12445 | d27eb4c79107c8cbd3f6f53f339cb11eeb41dcf4a7759a4b81f42d6caf1ea18e |
| tests/test_runs/results.json | 6152 | 28db409456be2fee071f75233961139e51b031eb11fa0cada38f9c0f2786386f |
| vendor/epubcheck/README.txt | 169 | ee6a4e3725cbf63fbab34ad9f2cee6d8019227917bc49b79ed37ee7bc913f1c2 |
| vendor/fonts/STIXTwo-OFL.txt | 4882 | bec17cee6412788db45fd2644b301afbc99cc5d372ddd3345dc4a7bfdefb9f04 |
| vendor/fonts/STIXTwoMath-Regular.otf | 838652 | f2076b9f1676438439dd41e23676f5ab99056e83d6b8f8c27841591ef2ccfa72 |
| vendor/fonts/SourceSerif4-Bold.otf | 251844 | f5fb9a7b1611353fdfebcf8b1e46c7d9108470f25999b841816d8b643b1856ff |
| vendor/fonts/SourceSerif4-BoldIt.otf | 175576 | ebb5394e1e11e09480619c9bb10f020aded9530833edcbdb735a4702ae6fa09e |
| vendor/fonts/SourceSerif4-It.otf | 169132 | f8062257f4693e438a8e317c9fe2b4393f0d4eed84d897edcbfd733c30a1c1a1 |
| vendor/fonts/SourceSerif4-LICENSE.md | 4492 | 75784a295293a8992f5a8d99210566e0064a012e6dab6731305e3787f15896c7 |
| vendor/fonts/SourceSerif4-Regular.otf | 241392 | edf160d0d584deee8a3bb2c3371b2a7624ca63580fbe02c57c1f4c91e84d8787 |
| vendor/fonts/SourceSerif4-Semibold.otf | 252852 | 25e034392847d9965c92f98971b3646436b7ab919ece9118b0c0e5ec94c02efc |
| vendor/fonts/SourceSerif4Display-Bold.otf | 275896 | c222fe7c8c0a715512c8e5aac26918c8cf3d8ba4a561cc2e5b2e76e49b988d03 |
| vendor/fonts/SourceSerif4Display-It.otf | 175300 | 653bba042213020d624a147c55d84662b3c20c1e12355bc691ae53c7051785ca |
| vendor/fonts/SourceSerif4Display-Regular.otf | 262988 | 0525aba71e1d7293d3ef645f5a9b56101432d1f6c676cba388f800523c7b2111 |
| vendor/fonts/SourceSerif4Display-Semibold.otf | 273232 | 0f2b3699c57dd032db8c8d93b34f7dac72e60fa2638d209aa2e428dfb6eb6400 |
| vendor/fonts/SourceSerif4SmText-Bold.otf | 254540 | 05f4aa92fb137675226b318335d7c44d2da86b7650bbf9b8fdf428a74139d3b5 |
| vendor/fonts/SourceSerif4SmText-BoldIt.otf | 177564 | 86679db08387aca6a7342c5f68f58e930c7d00d71a8ab1f07eb2b72fbc56b4c1 |
| vendor/fonts/SourceSerif4SmText-It.otf | 172992 | 220a0bf6d2a0c3fde644db2b2b602e725170ac1a90b0ce79994b7598c12980d1 |
| vendor/fonts/SourceSerif4SmText-Regular.otf | 245204 | 760327b0f9ef55310f11ed5c955693f4841f9b859407e98570d3654422a34d70 |

## XV. Remaining blockers

Only items that depend on future or external facts remain. The pipeline itself is engineered and tested, and font and toolchain installation is deterministic, so neither is a blocker.

**Release**
- RD-01: certified November 3, 2026 Florida result.
- RD-07: current family-case docket.
- RD-08: author confirmations and intended publication date.
- RD-02 to RD-06: refreshed at final execution.
- §58: records the release-verified master and its hash.

**Production evidence**
- ISBN mapping, ownership, and imprint (P9).
- The adopted cover source asset (P14).

**Authorization**
- The author's express final-production authorization.

**For author decision, not a production blocker**
- The endnote-heading mismatch in section XII, item 7.
