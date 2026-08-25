"""Create a rare-class-aware v5 development split without touching locked test.

The corrected manifest contains 51 development scenes and nine locked-test
scenes. This command deterministically reassigns only the development scenes so
validation contains at least one Outlet scene and two Door scenes. Locked-test
rows are copied verbatim and their files are never opened.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from training.annotation_workspace import PROJECT_DIR
from training.semantic_annotation_workspace import SEMANTIC_LABEL_IDS


DEFAULT_SOURCE_MANIFEST = (
    PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2_repaired"
    / "splits" / "split_manifest.json"
)
DEFAULT_OUTPUT_MANIFEST = DEFAULT_SOURCE_MANIFEST.with_name("v5_split_manifest.json")
DEFAULT_SEED = 260827
VALIDATION_COUNT = 9
DOOR_ID = 2
OUTLET_ID = 5


class V5SplitError(ValueError):
    """Raised when a safe, rare-aware v5 split cannot be created."""


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V5SplitError(f"manifest is missing or unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise V5SplitError("manifest root must be a JSON object")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tie(seed: int, scene_id: str) -> int:
    return int.from_bytes(
        hashlib.sha256(f"{seed}:{scene_id}".encode("utf-8")).digest()[:8], "big"
    )


def _class_ids(row: dict[str, object]) -> set[int]:
    values = row.get("class_ids_present")
    if not isinstance(values, list):
        raise V5SplitError(f"class presence is missing for {row.get('scene_id')}")
    result = {int(value) for value in values}
    if not result.issubset(set(SEMANTIC_LABEL_IDS)):
        raise V5SplitError(f"invalid class presence for {row.get('scene_id')}")
    return result


def _choose_validation(
    development_rows: list[dict[str, object]],
    *,
    seed: int,
    validation_count: int,
) -> set[str]:
    if validation_count <= 0 or validation_count >= len(development_rows):
        raise V5SplitError("validation count must leave non-empty train and validation sets")
    outlet_rows = [row for row in development_rows if OUTLET_ID in _class_ids(row)]
    door_rows = [row for row in development_rows if DOOR_ID in _class_ids(row)]
    if len(outlet_rows) < 2:
        raise V5SplitError("v5 requires at least two development Outlet scenes")
    if len(door_rows) < 3:
        raise V5SplitError("v5 requires at least three development Door scenes")

    selected: set[str] = set()

    def add_best(candidates: list[dict[str, object]], target_class: int) -> None:
        remaining = [row for row in candidates if str(row["scene_id"]) not in selected]
        if target_class == DOOR_ID:
            door_only = [row for row in remaining if OUTLET_ID not in _class_ids(row)]
            if door_only:
                remaining = door_only
        if not remaining:
            raise V5SplitError(f"cannot satisfy validation coverage for class {target_class}")
        # Prefer a scene that also covers the other rare class, then broader class coverage.
        other = DOOR_ID if target_class == OUTLET_ID else -1
        chosen = max(
            remaining,
            key=lambda row: (
                int(other in _class_ids(row)),
                len(_class_ids(row)),
                -_tie(seed, str(row["scene_id"])),
            ),
        )
        selected.add(str(chosen["scene_id"]))

    add_best(outlet_rows, OUTLET_ID)
    while sum(
        DOOR_ID in _class_ids(row)
        for row in development_rows
        if str(row["scene_id"]) in selected
    ) < 2:
        add_best(door_rows, DOOR_ID)

    class_totals = Counter()
    for row in development_rows:
        class_totals.update(_class_ids(row))
    targets = {
        class_id: class_totals[class_id] * validation_count / len(development_rows)
        for class_id in SEMANTIC_LABEL_IDS
    }

    while len(selected) < validation_count:
        current = Counter()
        for row in development_rows:
            if str(row["scene_id"]) in selected:
                current.update(_class_ids(row))

        def score(row: dict[str, object]) -> tuple[float, int]:
            after = current.copy()
            after.update(_class_ids(row))
            error = sum(
                (after[class_id] - targets[class_id]) ** 2
                / max(targets[class_id], 1.0)
                for class_id in SEMANTIC_LABEL_IDS
            )
            return (-error, -_tie(seed, str(row["scene_id"])))

        candidates = [
            row for row in development_rows if str(row["scene_id"]) not in selected
            and OUTLET_ID not in _class_ids(row)
        ]
        if not candidates:
            candidates = [
                row for row in development_rows if str(row["scene_id"]) not in selected
            ]
        selected.add(str(max(candidates, key=score)["scene_id"]))

    outlet_validation = sum(
        OUTLET_ID in _class_ids(row)
        for row in development_rows
        if str(row["scene_id"]) in selected
    )
    outlet_training = len(outlet_rows) - outlet_validation
    door_validation = sum(
        DOOR_ID in _class_ids(row)
        for row in development_rows
        if str(row["scene_id"]) in selected
    )
    if outlet_validation != 1 or outlet_training < 1 or door_validation < 2:
        raise V5SplitError("rare-class split constraints were not satisfied")
    return selected


def build_v5_split(
    source_path: Path = DEFAULT_SOURCE_MANIFEST,
    output_path: Path = DEFAULT_OUTPUT_MANIFEST,
    *,
    seed: int = DEFAULT_SEED,
    validation_count: int = VALIDATION_COUNT,
    project_dir: Path = PROJECT_DIR,
) -> dict[str, object]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    source = _load_json(source_path)
    required = {
        "dataset": "real_v2_repaired",
        "test_set_locked": True,
        "test_rows_reused_verbatim": True,
        "test_split_used": False,
    }
    for key, expected in required.items():
        if source.get(key) != expected:
            raise V5SplitError(f"corrected source manifest requires {key}={expected!r}")
    source_rows = source.get("scenes")
    if not isinstance(source_rows, list):
        raise V5SplitError("corrected source manifest has no scene rows")
    if any(not isinstance(row, dict) for row in source_rows):
        raise V5SplitError("corrected source manifest contains an invalid row")

    development = [row for row in source_rows if row.get("split") in {"train", "validation"}]
    test_rows = [row for row in source_rows if row.get("split") == "test"]
    source_counts = source.get("counts")
    if not isinstance(source_counts, dict):
        raise V5SplitError("corrected source manifest has no counts")
    expected_development = int(source_counts["train"]) + int(source_counts["validation"])
    if len(development) != expected_development or len(test_rows) != int(source_counts["test"]):
        raise V5SplitError("corrected source manifest count mismatch")
    ids = [str(row.get("scene_id") or "") for row in source_rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise V5SplitError("corrected source manifest has empty or duplicate scene IDs")

    validation_ids = _choose_validation(
        development, seed=seed, validation_count=validation_count
    )
    rows: list[dict[str, object]] = []
    for source_row in source_rows:
        row = dict(source_row)
        if row.get("split") != "test":
            row["split"] = (
                "validation" if str(row["scene_id"]) in validation_ids else "train"
            )
        rows.append(row)

    # Test rows must remain exactly equal, including paths and hashes.
    output_test_rows = [row for row in rows if row.get("split") == "test"]
    if output_test_rows != test_rows:
        raise V5SplitError("internal safety failure: locked-test rows changed")

    counts = {
        "train": len(development) - validation_count,
        "validation": validation_count,
        "test": len(test_rows),
    }
    class_presence = {
        split: {str(class_id): 0 for class_id in SEMANTIC_LABEL_IDS}
        for split in counts
    }
    for row in rows:
        for class_id in _class_ids(row):
            class_presence[str(row["split"])][str(class_id)] += 1

    manifest = dict(source)
    manifest.update(
        {
            "schema_version": 3,
            "created_from_manifest": source_path.relative_to(
                project_dir.resolve()
            ).as_posix(),
            "created_from_manifest_sha256": _sha256(source_path),
            "v5_split_seed": seed,
            "development_membership_rebalanced": True,
            "test_membership_preserved": True,
            "test_rows_reused_verbatim": True,
            "test_split_used": False,
            "counts": counts,
            "summary": {
                "counts": counts,
                "class_presence_by_split": class_presence,
                "overlap_check": "passed",
                "test_set_locked": True,
            },
            "policy": (
                "Only corrected train/validation membership was rebalanced for rare-class "
                "measurement. Locked-test rows were copied verbatim and test files were not opened."
            ),
            "scenes": rows,
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".part")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_MANIFEST)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    try:
        manifest = build_v5_split(args.source, args.output, seed=args.seed)
    except (OSError, KeyError, V5SplitError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    counts = manifest["counts"]
    presence = manifest["summary"]["class_presence_by_split"]
    print("BakeSmart v5 development split is ready")
    print(f"Training scenes:          {counts['train']}")
    print(f"Validation scenes:        {counts['validation']}")
    print(f"Validation Door scenes:   {presence['validation'][str(DOOR_ID)]}")
    print(f"Validation Outlet scenes: {presence['validation'][str(OUTLET_ID)]}")
    print(f"Locked test scenes:       {counts['test']} (unchanged; files unopened)")
    print("Locked test used:         NO")
    print(f"Manifest:                 {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
