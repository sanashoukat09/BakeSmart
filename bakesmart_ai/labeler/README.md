# BakeSmart Venue Mask Review Labeller

This local screen is now primarily for **review and small corrections** after
CVAT/SAM-assisted annotation.

BakeSmart keeps seven final mask IDs:

| ID | Class | How it is produced |
|---:|---|---|
| 0 | Wall | Human/CVAT |
| 1 | Floor | Human/CVAT |
| 2 | Door | Human/CVAT |
| 3 | Window | Human/CVAT |
| 4 | Furniture | Human/CVAT |
| 5 | Outlet | Human/CVAT |
| 6 | Walkway candidate | Derived automatically from Floor |

Draft masks may also contain internal value `255`, meaning **not labelled yet**.
A mask cannot be marked complete while any `255` pixels remain.

`Outlet` means an electrical wall/power socket.

## Recommended workflow

Do the main annotation in CVAT using the six human classes above and interactive
segmentation assistance such as SAM/SAM2 when available. Export as
`Segmentation Mask 1.1`, then run:

```powershell
python -m training.import_cvat_venue_masks `
  --archive "D:\path\to\venue_masks.zip" `
  --dataset real_v2 `
  --annotator-id sana-01 `
  --used-sam
```

Only pass `--used-sam` when SAM/SAM2 was actually used. See
`data/venue_vision/cvat/README.md` for the full workflow.

## Start the review screen

From `bakesmart_ai/`:

```powershell
python -m training.venue_labeler
```

Then open:

```text
http://127.0.0.1:8010
```

The server binds to `127.0.0.1` by default.

## Local data locations

The UI reads images from:

```text
data/venue_vision/raw/real_v2/images/
data/venue_vision/raw/gemini_synthetic_v1/images/
```

Masks and annotation sidecars stay under the local ignored
`data/venue_vision/raw/` workspace.

## Review workflow

1. Select the imported scene.
2. Check Wall, Floor, Door, Window, Furniture and Outlet boundaries.
3. Do not manually paint Walkway; class 6 is read-only and derived from Floor.
4. Use the missing-pixel finder if any `255` pixels remain.
5. Save corrections as a draft when needed.
6. Validate the mask.
7. Mark the annotation complete only when the six semantic classes are correct
   and the image has no unlabelled pixels.

A completed annotation remains:

```text
annotation_complete_pending_review
training_status = not_for_training
```

The independent reviewer must be a different person from the annotator.
