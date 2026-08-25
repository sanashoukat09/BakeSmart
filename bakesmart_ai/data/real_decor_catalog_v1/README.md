# BakeSmart real-decoration catalogue v1

This is the Stage 2 data foundation for realistic decoration suggestions. It
contains real-world decoration archetypes with dimensions, PKR planning ranges,
theme and event compatibility, venue constraints, safety profiles, market
evidence and rights-checked Wikimedia Commons photo candidates.

## What this dataset does

- Gives Stage 3 structured choices instead of repeating one synthetic item.
- Separates a planning price range from the observed source price.
- Links each item to a market source, safety profile and visual reference.
- Gives Stage 4 an automated path to retrieve reusable visual references.

## What this dataset does not do

- It does not change the live recommendation endpoint yet.
- Prices are observations and planning ranges, not vendor quotations.
- Market-source images are not copied or redistributed.
- A Commons page being listed does not permit a blind download. The collector
  must recheck the live API metadata and license before saving a file.
- Interrupted collection is safe to rerun: existing files are retained and
  hashed after the live rights metadata has been rechecked.
- This catalogue is not approved as machine-learning training data.

## Files

- `decor_items.csv`: 30 purchasable or rentable decoration archetypes.
- `market_sources.csv`: Pakistan-market price anchors and limitations.
- `photo_candidates.csv`: attribution-ready Commons inspiration candidates.
- `safety_profiles.csv`: placement and temporary-installation safeguards.
- `authoritative_sources.csv`: official rights and safety references.
- `manifest.json`: version boundary, file hashes and release status.

## Price interpretation

`observed_price_min` and `observed_price_max` reproduce the market observation
recorded on `observed_at`. `price_min_pkr` and `price_max_pkr` in the item table
are BakeSmart planning ranges inferred from those anchors. Delivery, labour,
venue restrictions, taxes, customization and availability can change the final
price, so Stage 3 must label every result as an estimate and request a vendor
quotation before purchase.

## Rights workflow

Only `CC0 1.0`, `CC BY 2.0`, `CC BY-SA 3.0`, and `CC BY-SA 4.0` candidates are
allowed in this version. Before an asset is downloaded, the collector checks
Wikimedia Commons `imageinfo/extmetadata`, rejects unknown or non-commercial
licenses, records attribution, and computes a SHA-256 hash. ShareAlike content
must remain clearly identified so later derivative handling can comply with its
license. Vendor and marketplace photos are evidence links only.

## Safety boundary

The catalogue provides conservative planning rules, not venue approval or an
engineering certificate. Installers must follow local law, manufacturer
instructions and the venue's rules. Exit routes and signs must remain visible,
temporary electrical products must suit the environment, and tall structures
must be secured against tipping.
