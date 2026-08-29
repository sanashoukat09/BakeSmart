"""Write BakeSmart's locally generated vertical-slice review GLBs to disk.

These files are for QA/review only. They are written to
`app/assets/review_vertical_slice/`, not to the production-asset directory.

Run from bakesmart_ai:
    python tools/generate_vertical_slice_assets.py
"""

from pathlib import Path

from app.services.vertical_slice_assets import (
    SPEC_BY_ASSET_ID,
    generate_review_asset_map,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PACKAGE_ROOT / "app" / "assets" / "review_vertical_slice"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for asset_id, data in generate_review_asset_map().items():
        spec = SPEC_BY_ASSET_ID[asset_id]
        output = OUTPUT_DIR / f"{spec.catalog_id}.glb"
        output.write_bytes(data)
        print(
            f"{asset_id}: {output.relative_to(PACKAGE_ROOT)} "
            f"{len(data)} bytes (review-only)"
        )


if __name__ == "__main__":
    main()
