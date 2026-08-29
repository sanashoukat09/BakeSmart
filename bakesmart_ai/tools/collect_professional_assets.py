"""Offline rights-safe downloader/planner for BakeSmart asset sources.

This tool does ordinary file retrieval only. It is not an AI service and is
never imported by BakeSmart's runtime recommendation or vision code.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = PACKAGE_ROOT / "data" / "professional_asset_sources_v1"
DEFAULT_OUTPUT = PACKAGE_ROOT / "assets" / "third_party_cc0" / "raw"
USER_AGENT = "BakeSmart-Professional-Asset-Collector/1.1"


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

    if asset_type in {"model", "model_pack"}:
        if "gltf" in joined or url.endswith((".glb", ".gltf", ".zip")):
            score -= 45
        if url.endswith(".glb"):
            score -= 15
    elif asset_type == "hdri":
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


def _plan_polyhaven(row: dict[str, str]) -> tuple[str, int | None, str | None]:
    slug = _polyhaven_slug(row)
    files = _request_json(f"https://api.polyhaven.com/files/{slug}")
    candidates = _flatten_files(files)
    if not candidates:
        raise RuntimeError(f"Poly Haven returned no downloadable files for {slug}")
    path, info = min(
        candidates,
        key=lambda item: _rank_candidate(row, item[0], item[1]),
    )
    return str(info["url"]), int(info.get("size") or 0) or None, info.get("md5")


def _download(
    url: str,
    destination: Path,
    expected_md5: str | None,
) -> tuple[int, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    md5 = hashlib.md5()
    size = 0
    temporary = destination.with_suffix(destination.suffix + ".part")
    with urlopen(request, timeout=120) as response, temporary.open("wb") as output:
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
    return size, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List the approved source queue.")
    parser.add_argument("--source-id", help="Plan one approved source.")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Actually download an automatically supported source.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = _rows()
    approved = [row for row in rows if _approved(row)]
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

    url, expected_size, expected_md5 = _plan_polyhaven(selected)
    filename = Path(urlparse(url).path).name or f'{selected["source_id"]}.bin'
    destination = args.output / selected["source_id"] / filename
    print(f"Planned file: {url}")
    print(f"Expected size: {expected_size or 'unknown'} bytes")
    print(f"Destination: {destination}")
    print(f"Expected MD5: {expected_md5 or 'not supplied'}")

    if not args.download:
        print("Dry run only. Re-run with --download after reviewing the plan.")
        return 0

    size, digest = _download(url, destination, expected_md5)
    print(f"Downloaded {size} bytes")
    print(f"MD5 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
