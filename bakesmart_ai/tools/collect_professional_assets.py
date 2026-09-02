"""Offline rights-safe downloader/planner for BakeSmart asset sources.

This tool performs ordinary file retrieval only. It is not an AI service and is
never imported by BakeSmart's runtime recommendation or vision code.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = PACKAGE_ROOT / "data" / "professional_asset_sources_v1"
DEFAULT_OUTPUT = PACKAGE_ROOT / "assets" / "third_party_cc0" / "raw"
DEFAULT_RECEIPT_DIR = REGISTRY_DIR / "download_receipts"
USER_AGENT = "BakeSmart-Professional-Asset-Collector/1.2"


def _registry_paths() -> list[Path]:
    paths = sorted(REGISTRY_DIR.glob("source_manifest*.csv"))
    if not paths:
        raise FileNotFoundError(f"No source manifests found in {REGISTRY_DIR}")
    return paths


def _rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in _registry_paths():
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                source_id = row.get("source_id", "").strip()
                if not source_id:
                    raise ValueError(f"{path.name} contains a blank source_id")
                if source_id in seen:
                    raise ValueError(f"Duplicate professional asset source id: {source_id}")
                seen.add(source_id)
                rows.append(row)
    return rows


def _approved(row: dict[str, str]) -> bool:
    return (
        row["collection_status"] == "approved_source"
        and row["license"] == "CC0-1.0"
        and row["license_verified"] == "true"
        and row["redistribution_allowed"] == "true"
        and row["ai_generated"] == "false"
    )


def _request_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _flatten_files(
    value: Any,
    path: tuple[str, ...] = (),
) -> list[tuple[tuple[str, ...], dict[str, Any]]]:
    output: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    if isinstance(value, dict):
        if isinstance(value.get("url"), str):
            output.append((path, value))
        for key, nested in value.items():
            if key in {"url", "size", "md5", "include"}:
                continue
            output.extend(_flatten_files(nested, path + (str(key),)))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            output.extend(_flatten_files(nested, path + (str(index),)))
    return output


def _rank_candidate(
    row: dict[str, str],
    path: tuple[str, ...],
    file_info: dict[str, Any],
) -> tuple[int, int]:
    joined = "/".join(path).lower()
    url = str(file_info.get("url", "")).lower()
    size = int(file_info.get("size") or 10**12)
    asset_type = row["asset_type"]
    score = 100

    if "1k" in joined:
        score -= 35
    elif "2k" in joined:
        score -= 30
    elif "4k" in joined:
        score -= 10

    if asset_type == "hdri":
        if url.endswith(".hdr"):
            score -= 50
        if "1k" in joined or "2k" in joined:
            score -= 15
    elif asset_type == "pbr_material":
        if url.endswith(".zip"):
            score -= 45
        if any(token in joined for token in ("diff", "rough", "normal", "arm", "metal")):
            score -= 10

    return score, size


def _polyhaven_slug(row: dict[str, str]) -> str:
    return urlparse(row["source_url"]).path.rstrip("/").split("/")[-1]


def _safe_relative_path(value: str) -> Path:
    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise RuntimeError(f"Unsafe included asset path from provider: {value!r}")
    return Path(*posix.parts)


def _filename_from_url(url: str, fallback: str) -> str:
    name = unquote(Path(urlparse(url).path).name)
    return name or fallback


def _polyhaven_model_plan(
    files: dict[str, Any],
    source_id: str,
) -> list[tuple[Path, str, int | None, str | None]]:
    gltf_tree = files.get("gltf")
    if not isinstance(gltf_tree, dict):
        raise RuntimeError(f"Poly Haven returned no glTF tree for model {source_id}")

    selected: dict[str, Any] | None = None
    for resolution in ("1k", "2k", "4k"):
        resolution_tree = gltf_tree.get(resolution)
        if not isinstance(resolution_tree, dict):
            continue
        for file_format in ("glb", "gltf"):
            candidate = resolution_tree.get(file_format)
            if isinstance(candidate, dict) and isinstance(candidate.get("url"), str):
                selected = candidate
                break
        if selected is not None:
            break
    if selected is None:
        raise RuntimeError(f"Poly Haven returned no 1K-4K glTF/GLB for model {source_id}")

    main_url = str(selected["url"])
    plan: list[tuple[Path, str, int | None, str | None]] = [
        (
            Path(_filename_from_url(main_url, f"{source_id}.gltf")),
            main_url,
            int(selected.get("size") or 0) or None,
            selected.get("md5"),
        )
    ]

    includes = selected.get("include")
    if isinstance(includes, dict):
        for include_path, include_info in includes.items():
            if not isinstance(include_info, dict) or not isinstance(include_info.get("url"), str):
                raise RuntimeError(f"Malformed include record for {source_id}: {include_path}")
            plan.append(
                (
                    _safe_relative_path(str(include_path)),
                    str(include_info["url"]),
                    int(include_info.get("size") or 0) or None,
                    include_info.get("md5"),
                )
            )
    return plan


def _polyhaven_texture_file(
    files: dict[str, Any],
    map_names: tuple[str, ...],
) -> dict[str, Any] | None:
    """Return the provider's 1K JPG record for the first matching map name."""

    by_lower_name = {str(key).lower(): value for key, value in files.items()}
    for map_name in map_names:
        map_tree = by_lower_name.get(map_name.lower())
        if not isinstance(map_tree, dict):
            continue
        one_k = map_tree.get("1k")
        if not isinstance(one_k, dict):
            continue
        candidate = one_k.get("jpg")
        if isinstance(candidate, dict) and isinstance(candidate.get("url"), str):
            return candidate
    return None


def _polyhaven_pbr_plan(
    files: dict[str, Any],
    source_id: str,
) -> list[tuple[Path, str, int | None, str | None]]:
    """Select a complete WebGL-ready 1K PBR set, never a single map."""

    required_maps = (
        ("base color", ("Diffuse", "diffuse")),
        ("OpenGL normal", ("nor_gl",)),
        ("packed ARM", ("arm",)),
    )
    optional_maps = (
        ("anisotropy strength", ("anisotropy_strength",)),
        ("anisotropy rotation", ("anisotropy_rotation",)),
    )
    selected: list[dict[str, Any]] = []
    missing: list[str] = []
    for label, names in required_maps:
        candidate = _polyhaven_texture_file(files, names)
        if candidate is None:
            missing.append(label)
        else:
            selected.append(candidate)
    if missing:
        raise RuntimeError(
            f"Poly Haven material {source_id} is missing required 1K JPG maps: "
            + ", ".join(missing)
        )
    for _label, names in optional_maps:
        candidate = _polyhaven_texture_file(files, names)
        if candidate is not None:
            selected.append(candidate)

    return [
        (
            Path(_filename_from_url(str(info["url"]), f"{source_id}.jpg")),
            str(info["url"]),
            int(info.get("size") or 0) or None,
            info.get("md5"),
        )
        for info in selected
    ]


def _plan_polyhaven(
    row: dict[str, str],
) -> list[tuple[Path, str, int | None, str | None]]:
    slug = _polyhaven_slug(row)
    files = _request_json(f"https://api.polyhaven.com/files/{slug}")

    if row["asset_type"] in {"model", "model_pack"}:
        return _polyhaven_model_plan(files, row["source_id"])
    if row["asset_type"] == "pbr_material":
        return _polyhaven_pbr_plan(files, row["source_id"])

    candidates = _flatten_files(files)
    if not candidates:
        raise RuntimeError(f"Poly Haven returned no downloadable files for {slug}")
    path, info = min(
        candidates,
        key=lambda item: _rank_candidate(row, item[0], item[1]),
    )
    url = str(info["url"])
    return [
        (
            Path(_filename_from_url(url, f"{row['source_id']}.bin")),
            url,
            int(info.get("size") or 0) or None,
            info.get("md5"),
        )
    ]


def _download(
    url: str,
    destination: Path,
    expected_md5: str | None,
) -> tuple[int, str, bool]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        existing_md5 = hashlib.md5()
        size = 0
        with destination.open("rb") as existing:
            while True:
                chunk = existing.read(1024 * 1024)
                if not chunk:
                    break
                existing_md5.update(chunk)
                size += len(chunk)
        digest = existing_md5.hexdigest()
        if expected_md5 and digest.lower() != expected_md5.lower():
            raise RuntimeError(
                f"existing file checksum mismatch for {destination.name}: "
                f"expected {expected_md5}, got {digest}"
            )
        return size, digest, False

    request = Request(url, headers={"User-Agent": USER_AGENT})
    md5 = hashlib.md5()
    size = 0
    temporary = destination.with_suffix(destination.suffix + ".part")
    with urlopen(request, timeout=180) as response, temporary.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            md5.update(chunk)
            size += len(chunk)
    digest = md5.hexdigest()
    if expected_md5 and digest.lower() != expected_md5.lower():
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"checksum mismatch for {destination.name}: "
            f"expected {expected_md5}, got {digest}"
        )
    os.replace(temporary, destination)
    return size, digest, True


def _verify_receipts(receipt_dir: Path, output_dir: Path) -> int:
    receipt_paths = sorted(receipt_dir.glob("*.json"))
    if not receipt_paths:
        print(f"No download receipts found in {receipt_dir}")
        return 1

    verified_files = 0
    verified_bytes = 0
    for receipt_path in receipt_paths:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        source_id = str(receipt["source_id"])
        for file_record in receipt["files"]:
            relative_path = _safe_relative_path(str(file_record["relative_path"]))
            asset_path = output_dir / source_id / relative_path
            if not asset_path.is_file():
                raise RuntimeError(f"Receipt file is missing: {asset_path}")
            size = asset_path.stat().st_size
            expected_size = int(file_record["size_bytes"])
            if size != expected_size:
                raise RuntimeError(
                    f"Receipt size mismatch for {asset_path}: "
                    f"expected {expected_size}, got {size}"
                )
            digest = hashlib.md5(asset_path.read_bytes()).hexdigest()
            expected_digest = str(file_record["md5"])
            if digest.lower() != expected_digest.lower():
                raise RuntimeError(
                    f"Receipt checksum mismatch for {asset_path}: "
                    f"expected {expected_digest}, got {digest}"
                )
            verified_files += 1
            verified_bytes += size
        print(f"Verified receipt: {source_id}")
    print(
        f"PASS: {len(receipt_paths)} receipts, {verified_files} files, "
        f"{verified_bytes} bytes"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List the approved source queue.")
    parser.add_argument("--source-id", help="Plan one approved source.")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Actually download an automatically supported source.",
    )
    parser.add_argument(
        "--verify-receipts",
        action="store_true",
        help="Verify every tracked receipt against the local raw workspace.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        default=DEFAULT_RECEIPT_DIR,
        help="Directory for tracked checksum and provenance receipts.",
    )
    args = parser.parse_args()

    rows = _rows()
    approved = [row for row in rows if _approved(row)]
    if args.verify_receipts:
        return _verify_receipts(args.receipt_dir, args.output)
    if args.list or not args.source_id:
        for row in approved:
            print(
                f'{row["source_id"]:34} {row["asset_type"]:12} '
                f'{row["provider"]:12} {row["title"]}'
            )
        print(f"\nManifest files: {len(_registry_paths())}")
        print(f"Approved source records: {len(approved)}")
        if not args.source_id:
            return 0

    selected = next(
        (row for row in approved if row["source_id"] == args.source_id),
        None,
    )
    if selected is None:
        raise SystemExit(f"Unknown or unapproved source id: {args.source_id}")

    print(f'Source: {selected["title"]}')
    print(f'Provider: {selected["provider"]}')
    print(f'License: {selected["license"]}')
    print(f'Page: {selected["source_url"]}')

    if selected["download_method"] != "polyhaven_api":
        print("Download mode: manual queue item.")
        print(
            "Reason: this provider does not expose a stable file metadata "
            "contract used by this helper."
        )
        return 0

    plan = _plan_polyhaven(selected)
    source_output = args.output / selected["source_id"]
    for relative_path, url, expected_size, expected_md5 in plan:
        destination = source_output / relative_path
        print(f"Planned file: {url}")
        print(f"Expected size: {expected_size or 'unknown'} bytes")
        print(f"Destination: {destination}")
        print(f"Expected MD5: {expected_md5 or 'not supplied'}")

    if not args.download:
        print("Dry run only. Re-run with --download after reviewing the plan.")
        return 0

    total = 0
    downloaded_files: list[dict[str, Any]] = []
    for relative_path, url, _expected_size, expected_md5 in plan:
        destination = source_output / relative_path
        size, digest, newly_downloaded = _download(url, destination, expected_md5)
        total += size
        downloaded_files.append(
            {
                "relative_path": relative_path.as_posix(),
                "source_url": url,
                "size_bytes": size,
                "md5": digest,
                "provider_md5": expected_md5,
            }
        )
        action = "Downloaded" if newly_downloaded else "Verified existing"
        print(f"{action} {size} bytes -> {destination}")
        print(f"MD5 {digest}")
    receipt = {
        "schema_version": 1,
        "source_id": selected["source_id"],
        "title": selected["title"],
        "provider": selected["provider"],
        "source_page": selected["source_url"],
        "license": selected["license"],
        "license_verified": selected["license_verified"] == "true",
        "redistribution_allowed": selected["redistribution_allowed"] == "true",
        "ai_generated": selected["ai_generated"] == "true",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "files": downloaded_files,
        "total_size_bytes": total,
    }
    args.receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = args.receipt_dir / f'{selected["source_id"]}.json'
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Receipt: {receipt_path}")
    print(f"Downloaded source bundle: {len(plan)} files, {total} bytes total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
