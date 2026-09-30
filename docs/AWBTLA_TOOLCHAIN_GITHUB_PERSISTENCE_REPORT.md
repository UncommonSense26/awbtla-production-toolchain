# AWBTLA Toolchain GitHub Persistence Report

Date: September 30, 2026.

This covers persistence and verification only:
- the manuscript was not obtained, modified, uploaded or built;
- §58 was not created;
- no book production was performed;
- Amazon KDP was not touched;
- no production parameter, source file, template, QA script or test fixture was changed.

## 1. Repository

| Item | Value |
|---|---|
| GitHub repository | UncommonSense26/awbtla-production-toolchain |
| Visibility | **PUBLIC**. Decided by the author on September 30, 2026, so the toolchain is available to others; this supersedes the earlier instruction to keep it private. |
| Remote URL | https://github.com/UncommonSense26/awbtla-production-toolchain |
| Default branch | main |
| GitHub Pages | Not enabled |
| License | MIT for the toolchain software; the fonts remain under the SIL Open Font License 1.1 (see LICENSE) |
| Tag | awbtla-toolchain-v1.0.0 (annotated), on the commit that adds this report |

## 2. History

The original commit was preserved unchanged, and nothing was squashed or rewritten.

| Commit | Purpose |
|---|---|
| 11faa725d8b1dd0614045184563e2f6e71162fd0 | Original imported commit: the toolchain, fonts and build report (39 files). |
| 261b19afc0255ecaad125c039adefdf66b8b6f2f | Security exclusions added to .gitignore (see §4). |
| 80ec6cfc296aeadb46ada02e28788f1f144c5f4a | MIT LICENSE added for public release. |
| (child of 80ec6cf) | Adds this report. This is the final HEAD and the tagged commit. Its SHA is recorded by the tag and in `git log`, because a file cannot contain the hash of the commit that adds it. |

Tracked files:
- 39 at the imported commit;
- 40 at 80ec6cf (plus LICENSE);
- 41 at the final HEAD (plus this report).

## 3. Pre-push verification of the imported archive

The archive AWBTLA_PRODUCTION_TOOLCHAIN_REPO_2026-09-29.zip (SHA-256 bc5cd98a4a0acb0057e32863354fa35b08e503ec4a0eff592fc79ab62b2b01f9) was extracted into a clean directory. There:
- it was a valid Git repository on branch `main`;
- HEAD was exactly 11faa725d8b1dd0614045184563e2f6e71162fd0;
- `git fsck --full` passed;
- the working tree was clean;
- 39 files were tracked;
- the toolchain was at `awbtla_production_toolchain/`.

A local clone also passed the full synthetic suite before anything was pushed.

## 4. Security and privacy review

Every tracked text file was reviewed before pushing. The review covered:
- passwords, API keys, tokens, cookies, and Amazon/KDP, GitHub and email credentials;
- manuscript text, correspondence, court records, ISBN correspondence and cover source files.

None was found.

- **The synthetic fixture.** It contains only generic filler text and the fictitious identifiers 2099-ZZ-000123 and 99-99999. Its SHA-256 is 8aa91601597907cb466d2f4d1da19151f83cf390ee9e99478ac20fce382ce24d. Its other identifiers are public legal citations or test-only ISBNs.
- **Publication metadata.** The only publication metadata committed is the placeholder template. The synthetic metadata uses checksum-valid test ISBNs, not assigned identifiers.
- **The historical build report** (tracked unchanged) names the private control files by SHA-256 only. It names release blockers (for example, "RD-07: current family-case docket") by label only, with no docket number or record content. The author accepted this for public release.

The .gitignore at 261b19a ignores:
- local `publication_metadata.yaml`, while `publication_metadata.template.yaml` stays tracked;
- manuscript masters (`AWBTLA_*MASTER*.md`, `.docx`);
- generated PDF, EPUB and DOCX files, production manifests and `AWBTLA_PRODUCTION_BUILD*/`;
- TeX temporaries, caches, build directories and `.env` files;
- test outputs (`tests/test_runs/`) and the downloaded EPUBCheck binaries.

`git ls-files -ci --exclude-standard` confirms that no tracked file is ignored.

## 5. Clean-clone verification from GitHub

The repository was cloned fresh from the GitHub remote into a new directory. No file came from the original extracted tree.

| Check | Result |
|---|---|
| Commit 11faa725… is in the remote main history | PASS |
| `git fsck --full` | PASS |
| Working tree clean after the clone, and again after the tests | PASS |
| `python3 install_dependencies.py` | PASS: all 14 fonts verified against deps.lock.json; EPUBCheck 5.1.0 downloaded and verified by SHA-256 |
| Canonical toolchain hash | eb22522cb5eb709d620113830224a2c7a5c8fcc35ae974ba0b286ac8c17b4ca8 (20 files). Matches the post-sanitization value. |
| `python3 tests/run_tests.py` | Exit 0 |

**Positive synthetic build**
- Exit 0 at 43 pages, using the production fonts rather than fallbacks.
- All ten required openings fell on rectos, and arabic page 1 is the Legal Notice.
- Bookmarks are nested, note links resolve both ways, and there are 13 internal link annotations.
- The long display broke into aligned lines, with 0 formula-overflow and 0 head-overflow markers.
- The signature-table headers are verbatim.
- The EPUB nav nests chapters under Parts, and MathML is present.

**QA**
- EPUBCheck 5.1.0: 0 fatal errors, 0 errors, 0 warnings.
- Print layout QA: 0 failures.
- PDF text-integrity QA: passed.
- EPUB QA, including text integrity: 0 failures.

**Reproducibility**
Two builds from identical inputs were byte-identical, and match the hashes in the persistence record.
- PDF: df622f0cf47f2253e8adc862b8d2dac509e471a59ccf523d02a88ccaed77736b (both builds).
- EPUB: 623851ca8215af1140195185b804544885c19423edbf66bc41d42dead743e79b (both builds).

**Negative tests: 9 of 9 passed**

| Test | Expected | Result |
|---|---|---|
| Wrong source hash | Exit 3, nothing created | Exit 3, no output directory. PASS |
| Missing authorization flag | Exit 4, nothing created | Exit 4, "PRODUCTION IS NOT AUTHORIZED", no output directory. PASS |
| Placeholder ISBN | Exit 5 | Exit 5, no output directory. PASS |
| Missing production font | Exit 6 | Exit 6, no output directory. PASS |
| Missing note | Exit 7 | Exit 7, "markers without entries: [4]". PASS |
| Oversized page count | Calibration ladder, then exit 8 | Exit 8 after 3 ladder builds, final PDF not created. PASS |
| Formula overflow | Exit 9 | Exit 9. PASS |
| Running-head overflow | Exit 9 | Exit 9. PASS |
| Text mismatch | QA failure | The tampered reference failed and the true reference passed. PASS |

The final tagged commit adds only this document. The suite was run a second time from a fresh GitHub clone of that commit before tagging, and the tag was created only after it passed.

## 6. Portability

No code fix was needed.

The documented system dependencies were installed from Ubuntu 24.04 packages:
- pandoc 3.1.3 and TeX Live 2023 (`texlive-luatex`, `texlive-latex-extra`, `texlive-fonts-recommended`, `texlive-latex-recommended`);
- `poppler-utils`;
- OpenJDK.

These match the tested versions.

PyYAML and pypdf were installed into a Python virtual environment. The verification container's system Python had a broken system `cryptography` package, which breaks importing pypdf. That fault belongs to the container, not the toolchain. A virtual environment (`python3 -m venv venv && venv/bin/pip install pyyaml pypdf`) is the recommended way to satisfy the README's Python requirement on any machine.

## 7. Durability

The toolchain can be rebuilt from nothing but this repository:

```
git clone https://github.com/UncommonSense26/awbtla-production-toolchain
cd awbtla-production-toolchain
git checkout awbtla-toolchain-v1.0.0
# system dependencies (Debian/Ubuntu):
sudo apt-get install pandoc texlive-luatex texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended poppler-utils default-jre
python3 -m venv venv && . venv/bin/activate && pip install pyyaml pypdf
cd awbtla_production_toolchain
python3 install_dependencies.py
python3 tests/run_tests.py
```

Production later requires the author to supply:
- the §58 release-verified manuscript;
- its expected SHA-256;
- a verified `publication_metadata.yaml`;
- the explicit `--authorize-production` flag (README §3; build report §XIII).

Every source file, template, QA script, test fixture, configuration file and font is committed. The only external artifact is EPUBCheck 5.1.0, which is pinned by URL and SHA-256 in deps.lock.json and verified on download. Nothing required remains only in a temporary Claude or ChatGPT environment.
