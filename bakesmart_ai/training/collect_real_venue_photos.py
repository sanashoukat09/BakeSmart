"""Collect rights-screened venue-photo candidates from Wikimedia Commons.

This collector is only a provenance and download tool. It does not call an AI
service, label pixels, approve images, or open the real-photo training gate.
Every downloaded candidate still requires visual privacy/venue review, manual
mask annotation, and an independent annotation review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageOps


COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "BakeSmart-FYP-VenueDataset/1.0 (educational dataset audit)"
DEFAULT_VENUE_ROOT = Path(__file__).resolve().parents[1] / "data" / "venue_vision"
DEFAULT_OUTPUT_DIR = DEFAULT_VENUE_ROOT / "raw" / "real_v2"
DEFAULT_MANIFEST = DEFAULT_VENUE_ROOT / "v2" / "source_candidates.csv"
DEFAULT_DISCOVERY_CACHE = DEFAULT_VENUE_ROOT / "v2" / "commons_discovery.json"

SOURCE_CATEGORIES = (
    "Banquet halls",
    "Ballrooms",
    "Dining rooms",
    "Living rooms",
    "Reception rooms",
    "Conference halls",
    "Function rooms",
    "Wedding venues",
    "Event venues",
    "Hotel lobbies",
    "Restaurant interiors",
    "Community halls",
    "Meeting rooms",
    "Conference rooms",
    "Hotel interiors",
    "Interiors of restaurants",
    "Assembly halls",
    "Community centers",
    "Convention centers",
    "Auditoriums",
    "Lobbies",
    "Foyers",
    "Exhibition halls",
    "Theatre interiors",
    "Wedding halls",
    "Party rooms",
)

ALLOWED_LICENSE_PATTERNS = (
    re.compile(r"^CC0(?:\s|$)", re.IGNORECASE),
    re.compile(r"^CC BY (?:2\.0|2\.5|3\.0|4\.0)(?:\s|$)", re.IGNORECASE),
    re.compile(r"^Public domain$", re.IGNORECASE),
    re.compile(r"^Public Domain Mark", re.IGNORECASE),
)
DISALLOWED_LICENSE_TOKENS = ("BY-SA", "NC", "ND", "GFDL")
PEOPLE_RISK_TERMS = (
    "audience",
    "bride",
    "child",
    "children",
    "crowd",
    "groom",
    "guest",
    "people",
    "person",
    "portrait",
    "speaker",
    "tourist",
    "visitor",
    "wedding ceremony",
)
UNSUITABLE_TERMS = (
    "architectural drawing",
    "diagram",
    "engraving",
    "floor plan",
    "map",
    "painting",
    "poster",
    "render",
    "sketch",
)
MANIFEST_COLUMNS = (
    "candidate_id",
    "commons_page_id",
    "title",
    "source_category",
    "source_page_url",
    "original_url",
    "download_url",
    "license",
    "license_url",
    "creator",
    "credit",
    "attribution_required",
    "modifications",
    "image_path",
    "image_sha256",
    "perceptual_hash",
    "pixel_width",
    "pixel_height",
    "visual_venue_review",
    "visual_people_review",
    "rights_review",
    "selection_status",
    "review_notes",
)
SOURCE_AUDIT_COLUMNS = (
    "commons_page_id",
    "title",
    "source_category",
    "source_page_url",
    "original_url",
    "download_url",
    "license",
    "license_url",
    "creator",
    "credit",
    "automated_license_screen",
    "training_status",
)


@dataclass(frozen=True)
class CommonsCandidate:
    page_id: int
    title: str
    source_category: str
    source_page_url: str
    original_url: str
    download_url: str
    license_name: str
    license_url: str
    creator: str
    credit: str
    source_width: int
    source_height: int


def _plain_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(without_tags).split())


def _metadata_value(metadata: dict[str, object], key: str) -> str:
    item = metadata.get(key)
    if not isinstance(item, dict):
        return ""
    value = item.get("value", "")
    return _plain_text(str(value))


def _compact_download_url(url: str) -> str:
    return re.sub(r"/960px-", "/480px-", url)


def _clean_wikimedia_download_url(url: str) -> str:
    """Keep the canonical file address but remove nonessential tracking query."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.netloc.casefold() == "upload.wikimedia.org":
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, "", "")
        )
    return url


def _request_json(parameters: dict[str, str], *, retries: int = 4) -> dict:
    query = urllib.parse.urlencode(
        {"format": "json", "formatversion": "2", **parameters}
    )
    request = urllib.request.Request(
        f"{COMMONS_API_URL}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        except (OSError, TimeoutError, json.JSONDecodeError):
            if attempt + 1 == retries:
                raise
            time.sleep(1.0 + attempt)
    raise RuntimeError("unreachable")


def _license_allowed(name: str) -> bool:
    if any(token.lower() in name.lower() for token in DISALLOWED_LICENSE_TOKENS):
        return False
    return any(pattern.search(name.strip()) for pattern in ALLOWED_LICENSE_PATTERNS)


def _looks_suitable(text: str) -> bool:
    lowered = text.lower()
    return not any(term in lowered for term in (*PEOPLE_RISK_TERMS, *UNSUITABLE_TERMS))


def _category_candidates(category: str) -> list[CommonsCandidate]:
    candidates: list[CommonsCandidate] = []
    continuation = ""
    while len(candidates) < 240:
        parameters = {
            "action": "query",
            "generator": "categorymembers",
            "gcmtitle": f"Category:{category}",
            "gcmtype": "file",
            "gcmlimit": "500",
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
            "iiurlwidth": "480",
        }
        if continuation:
            parameters["gcmcontinue"] = continuation
        result = _request_json(
            parameters
        )
        for page in result.get("query", {}).get("pages", []):
            image_info_rows = page.get("imageinfo", [])
            if not image_info_rows:
                continue
            image_info = image_info_rows[0]
            mime = str(image_info.get("mime", ""))
            width = int(image_info.get("width", 0))
            height = int(image_info.get("height", 0))
            if mime not in {"image/jpeg", "image/png"} or min(width, height) < 480:
                continue
            aspect = width / max(height, 1)
            if not 0.75 <= aspect <= 2.4:
                continue
            metadata = image_info.get("extmetadata", {})
            license_name = _metadata_value(metadata, "LicenseShortName")
            if not _license_allowed(license_name):
                continue
            combined_text = " ".join(
                (
                    str(page.get("title", "")),
                    _metadata_value(metadata, "ImageDescription"),
                    _metadata_value(metadata, "Categories"),
                )
            )
            if not _looks_suitable(combined_text):
                continue
            thumb_url = str(image_info.get("thumburl", ""))
            original_url = str(image_info.get("url", ""))
            source_page_url = str(image_info.get("descriptionurl", ""))
            if not thumb_url or not original_url or not source_page_url:
                continue
            candidates.append(
                CommonsCandidate(
                    page_id=int(page["pageid"]),
                    title=str(page["title"]),
                    source_category=category,
                    source_page_url=source_page_url,
                    original_url=original_url,
                    download_url=_compact_download_url(thumb_url),
                    license_name=license_name,
                    license_url=_metadata_value(metadata, "LicenseUrl"),
                    creator=_metadata_value(metadata, "Artist") or "Unknown",
                    credit=_metadata_value(metadata, "Credit") or "Wikimedia Commons",
                    source_width=width,
                    source_height=height,
                )
            )
        continuation = result.get("continue", {}).get("gcmcontinue", "")
        if not continuation:
            break
    return candidates[:240]


def discover_candidates(
    categories: tuple[str, ...] = SOURCE_CATEGORIES,
    *,
    cache_path: Path = DEFAULT_DISCOVERY_CACHE,
) -> list[CommonsCandidate]:
    cached_candidates: list[CommonsCandidate] = []
    scanned_categories: set[str] = set()
    if cache_path.is_file():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        cached_candidates = []
        for row in cached.get("candidates", []):
            normalized = dict(row)
            normalized["download_url"] = _compact_download_url(
                str(normalized["download_url"])
            )
            cached_candidates.append(CommonsCandidate(**normalized))
        scanned_categories = set(
            cached.get(
                "categories",
                [item.source_category for item in cached_candidates],
            )
        )
        if set(categories).issubset(scanned_categories):
            return cached_candidates
    by_page: dict[int, CommonsCandidate] = {
        candidate.page_id: candidate for candidate in cached_candidates
    }
    for category in categories:
        if category in scanned_categories:
            continue
        print(f"SCANNING: Category:{category}", flush=True)
        for candidate in _category_candidates(category):
            by_page.setdefault(candidate.page_id, candidate)
    grouped: dict[str, deque[CommonsCandidate]] = defaultdict(deque)
    for candidate in sorted(
        by_page.values(), key=lambda item: (item.source_category, item.title.casefold())
    ):
        grouped[candidate.source_category].append(candidate)
    ordered: list[CommonsCandidate] = []
    while any(grouped.values()):
        for category in categories:
            if grouped[category]:
                ordered.append(grouped[category].popleft())
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_payload = {
        "categories": list(categories),
        "source": COMMONS_API_URL,
        "candidates": [asdict(item) for item in ordered],
    }
    cache_path.write_text(
        f"{json.dumps(cache_payload, indent=2, ensure_ascii=False, sort_keys=True)}\n",
        encoding="utf-8",
    )
    return ordered


def _download_cache_path(download_dir: Path, candidate: CommonsCandidate) -> Path:
    return download_dir / f"{candidate.page_id}.source"


def _curl_batch(
    transfers: list[tuple[str, Path]],
    *,
    maximum_bytes: int | None,
) -> None:
    if not transfers:
        return
    command = [
        "curl",
        "--parallel",
        "--parallel-immediate",
        "--parallel-max",
        "4",
    ]
    for url, output_path in transfers:
        command.extend(
            [
                "--fail",
                "--silent",
                "--show-error",
                "--location",
                "--connect-timeout",
                "10",
                "--max-time",
                "45",
                "--retry",
                "1",
                "--retry-all-errors",
                "--remove-on-error",
                "--user-agent",
                USER_AGENT,
            ]
        )
        if maximum_bytes is not None:
            command.extend(["--max-filesize", str(maximum_bytes)])
        command.extend(["--output", str(output_path), url, "--next"])
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=max(180, len(transfers) * 18),
    )
    if result.returncode:
        print(
            "WARNING: some Commons transfers failed and will be skipped or retried",
            flush=True,
        )


def _prefetch_candidates(
    candidates: list[CommonsCandidate],
    download_dir: Path,
) -> None:
    download_dir.mkdir(parents=True, exist_ok=True)
    missing = [
        candidate
        for candidate in candidates
        if not _download_cache_path(download_dir, candidate).is_file()
    ]
    print(f"PREFETCHING: {len(missing)} thumbnails", flush=True)
    _curl_batch(
        [
            (candidate.download_url, _download_cache_path(download_dir, candidate))
            for candidate in missing
        ],
        maximum_bytes=5_000_000,
    )
    still_missing = [
        candidate
        for candidate in missing
        if not _download_cache_path(download_dir, candidate).is_file()
    ]
    print(f"FALLBACK: {len(still_missing)} original files", flush=True)
    _curl_batch(
        [
            (
                _clean_wikimedia_download_url(candidate.original_url),
                _download_cache_path(download_dir, candidate),
            )
            for candidate in still_missing
        ],
        maximum_bytes=15_000_000,
    )


def write_source_audit(
    candidates: list[CommonsCandidate],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=SOURCE_AUDIT_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(
                {
                    "commons_page_id": candidate.page_id,
                    "title": candidate.title,
                    "source_category": candidate.source_category,
                    "source_page_url": candidate.source_page_url,
                    "original_url": candidate.original_url,
                    "download_url": candidate.download_url,
                    "license": candidate.license_name,
                    "license_url": candidate.license_url,
                    "creator": candidate.creator,
                    "credit": candidate.credit,
                    "automated_license_screen": "passed",
                    "training_status": "candidate_not_for_training",
                }
            )


def _normalise_image(payload: bytes) -> Image.Image:
    with Image.open(io.BytesIO(payload)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((640, 640), Image.Resampling.LANCZOS)
        return image.copy()


def _prepare_candidate(
    item: tuple[CommonsCandidate, Path],
) -> tuple[CommonsCandidate, Image.Image, str] | None:
    candidate, source_path = item
    try:
        image = _normalise_image(source_path.read_bytes())
    except (OSError, TimeoutError):
        return None
    return candidate, image, _perceptual_hash(image)


def _perceptual_hash(image: Image.Image) -> str:
    small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    bits = []
    for row in range(8):
        offset = row * 9
        bits.extend(
            pixels[offset + column] > pixels[offset + column + 1]
            for column in range(8)
        )
    value = sum(int(bit) << index for index, bit in enumerate(bits))
    return f"{value:016x}"


def _hash_distance(first: str, second: str) -> int:
    return (int(first, 16) ^ int(second, 16)).bit_count()


def collect(
    *,
    target_count: int,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> list[dict[str, str]]:
    if target_count < 100:
        raise ValueError("real venue collection must request at least 100 candidates")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    accepted_hashes: list[str] = []
    candidates = discover_candidates()
    write_source_audit(candidates, manifest_path.parent / "source_audit.csv")
    download_dir = output_dir / "downloads"
    _prefetch_candidates(candidates, download_dir)
    with ThreadPoolExecutor(max_workers=4) as executor:
        for start in range(0, len(candidates), 32):
            batch = candidates[start : start + 32]
            prepared_rows = list(
                executor.map(
                    _prepare_candidate,
                    [
                        (candidate, _download_cache_path(download_dir, candidate))
                        for candidate in batch
                    ],
                )
            )
            for prepared in prepared_rows:
                if prepared is None:
                    continue
                candidate, image, perceptual_hash = prepared
                if any(
                    _hash_distance(perceptual_hash, seen) <= 3
                    for seen in accepted_hashes
                ):
                    continue
                candidate_id = f"commons-venue-{len(rows) + 1:04d}"
                image_path = output_dir / "images" / f"{candidate_id}.jpg"
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(image_path, format="JPEG", quality=90, optimize=True)
                payload = image_path.read_bytes()
                accepted_hashes.append(perceptual_hash)
                rows.append(
                    {
                        "candidate_id": candidate_id,
                        "commons_page_id": str(candidate.page_id),
                        "title": candidate.title,
                        "source_category": candidate.source_category,
                        "source_page_url": candidate.source_page_url,
                        "original_url": candidate.original_url,
                        "download_url": candidate.download_url,
                        "license": candidate.license_name,
                        "license_url": candidate.license_url,
                        "creator": candidate.creator,
                        "credit": candidate.credit,
                        "attribution_required": str(
                            not candidate.license_name.lower().startswith(
                                ("cc0", "public")
                            )
                        ).lower(),
                        "modifications": "resized to maximum 640 px; converted to RGB JPEG; EXIF removed",
                        "image_path": os.path.relpath(
                            image_path, manifest_path.parent
                        ),
                        "image_sha256": hashlib.sha256(payload).hexdigest(),
                        "perceptual_hash": perceptual_hash,
                        "pixel_width": str(image.width),
                        "pixel_height": str(image.height),
                        "visual_venue_review": "pending",
                        "visual_people_review": "pending",
                        "rights_review": "metadata_screen_passed_manual_review_pending",
                        "selection_status": "candidate_not_for_training",
                        "review_notes": "",
                    }
                )
                print(
                    f"COLLECTED {len(rows):03d}/{target_count}: "
                    f"{candidate.source_category} — {candidate.title}",
                    flush=True,
                )
                if len(rows) >= target_count:
                    break
            if len(rows) >= target_count:
                break
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    if len(rows) < target_count:
        raise RuntimeError(
            f"only {len(rows)} eligible candidates were collected; "
            f"requested {target_count}; partial manifest was written"
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-count", type=int, default=140)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        rows = collect(
            target_count=args.target_count,
            output_dir=args.output_dir,
            manifest_path=args.manifest,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(
        f"PASS: collected {len(rows)} rights-screened venue candidates; "
        "all remain blocked from training pending visual and annotation review"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
