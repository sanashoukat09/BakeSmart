# BakeSmart Venue Mask Labeller

This is BakeSmart's local annotation screen for real and synthetic venue masks.
It is designed to keep annotation fast without requiring a separate annotation
platform.

BakeSmart keeps seven final mask IDs:

| ID | Class | How it is produced |
|---:|---|---|
| 0 | Wall | Human annotation |
| 1 | Floor | Human annotation |
| 2 | Door | Human annotation |
| 3 | Window | Human annotation |
| 4 | Furniture | Human annotation |
| 5 | Outlet | Human annotation |
| 6 | Walkway candidate | Derived automatically from Floor |

Draft masks may also contain internal value `255`, meaning **not labelled yet**.
A mask cannot be marked complete while any `255` pixels remain.

`Outlet` means an electrical wall/power socket.

## Start the labeller

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

## Fast annotation workflow

Use the built-in smart tools instead of painting every pixel with the brush:

1. Use **Polygon Fill** for large Wall and Floor regions.
2. Use **Smart Object** for Furniture, Door, Window and other bounded objects.
3. Use the brush only for small corrections and Outlet regions when necessary.
4. Walkway is read-only and is generated from Floor by BakeSmart.
5. Use the missing-pixel finder if any `255` pixels remain.
6. Save drafts while working.
7. Validate the mask.
8. Mark the annotation complete only when the semantic classes are correct and
   no unlabelled pixels remain.

A completed annotation remains:

```text
annotation_complete_pending_review
training_status = not_for_training
```

The independent reviewer must be a different person from the annotator.
