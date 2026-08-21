# CVAT/SAM-assisted venue annotation workflow

BakeSmart now uses CVAT as the fast annotation workspace for real venue masks.
The final BakeSmart model is still trained separately; CVAT/SAM is only an
annotation aid.

## Classes to create in CVAT

Create exactly these six semantic labels:

1. `wall`
2. `floor`
3. `door`
4. `window`
5. `furniture`
6. `outlet`

Do **not** create a `walkway` label. BakeSmart derives class 6 (`Walkway
candidate`) automatically from the interior of the labelled floor after import.

`outlet` means an electrical wall/power socket. Small switchboards can be
included with the outlet region when they are part of the same power point.

## Annotation rule

Every visible pixel that belongs to the venue scene should be assigned to one
of the six labels above. Use CVAT's interactive segmentation assistance (for
example SAM/SAM2 when available) to create accurate regions quickly, then make
small manual corrections in CVAT.

Unannotated/background pixels are imported as BakeSmart value `255`
(`unlabelled`). If any remain, the scene stays `draft_in_progress` and the local
BakeSmart missing-pixel finder can show where the gaps are.

## Export from CVAT

Export the finished task in:

```text
Segmentation Mask 1.1
```

BakeSmart expects the official CVAT ZIP structure containing `labelmap.txt` and
class masks under `SegmentationClass/`. RGB, paletted and grayscale/indexed PNG
class masks are supported.

The mask filename must match the local BakeSmart scene ID. For example:

```text
source image: data/venue_vision/raw/real_v2/images/real-venue-0001.jpg
CVAT mask:    SegmentationClass/real-venue-0001.png
```

`real-venue-0001.jpg.png` is also accepted.

## Validate without writing anything

From `bakesmart_ai/`:

```powershell
python -m training.import_cvat_venue_masks `
  --archive "D:\path\to\venue_masks.zip" `
  --dataset real_v2 `
  --annotator-id sana-01 `
  --dry-run
```

The importer checks the label map, image/mask dimensions, scene IDs and mask
colours/indices before it changes local data.

## Import

If you actually used SAM/SAM2 while annotating in CVAT:

```powershell
python -m training.import_cvat_venue_masks `
  --archive "D:\path\to\venue_masks.zip" `
  --dataset real_v2 `
  --annotator-id sana-01 `
  --used-sam
```

If you did not use SAM/SAM2, omit `--used-sam`; BakeSmart will record the import
as a normal CVAT manual import.

If a scene already has an unfinished local mask and you intentionally want the
CVAT version to replace it, add `--replace-existing`.

A mask already marked `annotation_complete_pending_review` is never overwritten
by this importer.

## Automatic walkway generation

The importer first restores any old Walkway pixels to Floor, then identifies
floor pixels that are sufficiently far from visible non-floor boundaries. Those
interior floor pixels become class 6 (`Walkway candidate`). Small isolated
candidate regions are removed.

This is intentionally called a **visual walkway candidate**. Pixel spacing in a
single photo does not prove a real-world 90 cm clearance. Metric safety remains
based on user-confirmed measurements and the later placement logic.

## What gets saved

For each imported scene BakeSmart saves:

- the seven-class single-channel PNG mask under the local ignored `masks/`
  directory;
- the annotation sidecar under `annotation_records/`;
- CVAT archive provenance and hash;
- whether SAM/SAM2 assistance was actually used;
- automatic-walkway provenance;
- `training_status = not_for_training` until independent review.

If all pixels were labelled, the imported annotation becomes
`annotation_complete_pending_review`. If background/unlabelled pixels remain,
it stays `draft_in_progress`.

## Final review

After import, start the local BakeSmart review screen:

```powershell
python -m training.venue_labeler
```

Open `http://127.0.0.1:8010`. Class 6 is read-only because Walkway is derived,
not manually painted. Use the screen to inspect/correct the six human classes
and locate any remaining unlabelled gaps.

A different person must perform the independent review before a real mask is
approved for model training.
