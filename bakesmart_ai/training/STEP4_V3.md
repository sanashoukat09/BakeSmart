# Real venue Step 4 v3

Use v3 after the v1/v2 validation experiments if v2 over-emphasizes Outlet and reduces overall segmentation quality.

Run from `bakesmart_ai`:

```powershell
python -m training.train_real_venue_segmentation_v3
```

v3 keeps the exact locked Step-3 split and does not modify images, masks, v1, or v2 outputs. It trains a fresh six-class U-Net from random weights and never loads the nine locked test scenes.

Default training views per epoch are:

- one full-room view for every training scene;
- one random crop for every training scene;
- two Door-focused crops for each training scene that contains Door;
- two Outlet-focused crops for each training scene that contains Outlet.

With the current 42-scene training split (19 Door scenes and 41 Outlet scenes), this gives 42 full views, 42 random views, 38 Door-focused views and 82 Outlet-focused views, for 204 training views per epoch.

Rare-class loss weights are deliberately more moderate than v2. Checkpoint selection uses a balanced validation score:

`0.80 * validation mIoU + 0.10 * Door IoU + 0.10 * Outlet IoU`

This keeps overall segmentation quality dominant while still rewarding real improvement on the two rare classes.

Outputs are separate:

- `models/venue_vision_real_v3/best_model.pt`
- `models/venue_vision_real_v3/validation_report.json`

Do not evaluate the locked test set until v3 is compared with the v1 and v2 validation results and the Step-4 configuration is frozen.
