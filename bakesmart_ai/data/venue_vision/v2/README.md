# Real Venue Collection v2

This directory is the Phase 12 provenance-first collection workspace. It does
not yet contain an approved real-photo training dataset.

## Current status

- `commons_discovery.json` freezes 176 Wikimedia Commons candidates discovered
  on 2026-08-18.
- `source_audit.csv` exposes the per-file source page, original URL, creator,
  licence and licence URL in a reviewable table.
- `source_candidates.csv` contains 74 downloaded, source-linked candidates
  from the audited catalogue. All are pending human suitability, privacy and
  rights review; none are training data.
- `visual_prescreen_v1.csv` records the AI-assisted visual screen: 33
  candidates remain pending human review and 41 are rejected. This is not a
  substitute for the required human privacy, suitability and rights review.
- Every source row remains `candidate_not_for_training`.
- No real image or mask is committed. Transfer files stay under ignored
  `../raw/real_v2/` storage.
- `real_annotations_template.csv` is intentionally header-only because no mask
  has completed manual annotation and independent review.

Only CC0, public-domain and CC BY 2.0/2.5/3.0/4.0 metadata passed the automated
screen. CC BY-SA, non-commercial, no-derivatives and GFDL records were excluded.
This screen is not a legal warranty. A reviewer must open each Commons file
page, verify its current terms and attribution, reject privacy/personality-right
risks, and confirm that the file is a real venue photograph.

Wikimedia Commons explains that files are freely licensed or public domain but
that reusers remain responsible for following the licence on each file page and
for checking non-copyright restrictions:

- <https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia>
- <https://commons.wikimedia.org/wiki/Commons:Licensing>

The accepted Creative Commons licences allow adaptation; CC BY additionally
requires appropriate credit, a licence link and disclosure of modifications:

- <https://creativecommons.org/publicdomain/zero/1.0/>
- <https://creativecommons.org/licenses/by/4.0/>

## Approval workflow

1. Run `python -m training.collect_real_venue_photos --target-count 140` from
   `bakesmart_ai/` in a network environment that permits Commons downloads.
2. Bind every local image to its source row using the Commons page ID and record
   the downloaded file SHA-256.
3. Reject drawings, renders, exteriors, duplicates, faces/people, unreadable
   rooms and photos without a useful wall/floor view.
4. Manually draw a same-size single-channel PNG mask. IDs remain: wall `0`,
   floor `1`, door `2`, window `3`, furniture `4`, outlet `5`, walkway candidate
   `6`. A walkway is only a possible clear-floor region; it never becomes a
   confirmed circulation route without customer confirmation.
5. Have a different reviewer inspect the source rights, photo suitability and
   every mask boundary. Annotator and reviewer IDs must differ.
6. Add only independently approved rows to the final manifest, split by whole
   venue/photographer group, and rerun the dataset validator.

The gate requires at least 100 independently approved rows, including a locked
real-photo test split. Until then BakeSmart must continue to report its current
vision output as synthetic-bootstrap, low-confidence candidates only.
