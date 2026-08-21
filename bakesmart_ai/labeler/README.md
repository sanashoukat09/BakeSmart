# BakeSmart Venue Mask Labeller

This is a local-only annotation screen for the seven BakeSmart venue-vision
classes:

| ID | Class |
|---:|---|
| 0 | Wall |
| 1 | Floor |
| 2 | Door |
| 3 | Window |
| 4 | Furniture |
| 5 | Outlet |
| 6 | Walkway candidate |

Draft masks may also contain internal value `255`, which means **not labelled
yet**. A mask cannot be marked complete while any `255` pixels remain.

## Start the labeller

From `bakesmart_ai/`:

```powershell
python -m training.venue_labeler
```

Then open:

```text
http://127.0.0.1:8010
```

The server binds to `127.0.0.1` by default so the annotation workspace is not
exposed to other devices on the network.

## Local data locations

The UI reads images from:

```text
data/venue_vision/raw/real_v2/images/
data/venue_vision/raw/gemini_synthetic_v1/images/
```

It writes masks to the matching local `masks/` folder and writes annotation
sidecars to the matching `annotation_records/` folder. Those paths are under
`data/venue_vision/raw/`, which is ignored by the BakeSmart AI `.gitignore`.

A completed annotation is still recorded as:

```text
annotation_complete_pending_review
training_status = not_for_training
```

Completion therefore does **not** approve an image for training. The later
independent-review workflow must confirm the image, rights/privacy decision and
mask before it can enter the real training manifest.

## Suggested labelling workflow

1. Select the dataset and scene.
2. Enter your annotator ID.
3. Select the dominant class and use **Fill entire image**.
4. Paint the remaining wall/floor/door/window/furniture/outlet/walkway regions.
5. Use zoom for small outlets and narrow boundaries.
6. Use **Save draft** whenever you want to stop and continue later.
7. Use **Validate mask** to check whether any unlabelled pixels remain.
8. Use **Mark annotation complete** only after the entire image is correctly labelled.

The annotator must not act as the independent reviewer for the same image.
