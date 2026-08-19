"""Generate provenance-tracked synthetic venue images with the Gemini API.

This is an optional external-data augmentation tool. Generated images remain
synthetic, unlabelled and blocked from training until suitability review and
seven-class mask annotation are complete. They are never valid real-photo test
data.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps


DEFAULT_MODEL = "gemini-2.5-flash-image"
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
USER_AGENT = "BakeSmart-FYP-SyntheticVenueGenerator/1.0"
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "venue_vision"
    / "raw"
    / "gemini_synthetic_v1"
)
MANIFEST_COLUMNS = (
    "generation_id",
    "prompt_index",
    "prompt_sha256",
    "model",
    "generated_at_utc",
    "provider",
    "synthetic_status",
    "training_status",
    "prompt",
    "image_path",
    "image_sha256",
    "mime_type",
    "pixel_width",
    "pixel_height",
    "response_text",
)

VENUE_TYPES = (
    "small residential living room suitable for a birthday setup",
    "medium community function room",
    "modern hotel banquet room",
    "wedding reception hall before decoration",
    "restaurant private dining room",
    "corporate conference room",
    "bright indoor party room",
    "large ballroom before event setup",
    "compact bakery celebration consultation room",
    "multipurpose indoor event hall",
)
ROOM_SIZES = (
    "compact 3 by 4 metre",
    "small 4 by 5 metre",
    "medium 6 by 8 metre",
    "wide 8 by 12 metre",
    "large 12 by 18 metre",
)
LIGHTING = (
    "soft daylight from the side windows",
    "neutral ceiling lighting with mild daylight",
    "warm evening ceiling lighting",
    "bright overcast daylight",
)
FLOORS = (
    "light tile floor",
    "medium wood floor",
    "neutral carpeted floor",
    "polished concrete floor",
)
FURNITURE = (
    "mostly empty with one plain movable table and four chairs",
    "lightly furnished with stackable chairs along one wall",
    "a few neutral tables and chairs leaving a broad clear centre",
    "one sofa and one plain table positioned away from the main wall",
)
VIEWPOINTS = (
    "eye-level wide-angle view from a corner",
    "eye-level view facing the main setup wall",
    "slightly elevated wide view from the entrance",
    "wide view showing two adjacent walls and most of the floor",
)


def build_prompt(prompt_index: int) -> str:
    """Create a deterministic, diverse prompt from a one-based index."""
    if prompt_index < 1:
        raise ValueError("prompt index must be at least 1")
    index = prompt_index - 1
    venue = VENUE_TYPES[index % len(VENUE_TYPES)]
    room_size = ROOM_SIZES[(index // len(VENUE_TYPES)) % len(ROOM_SIZES)]
    lighting = LIGHTING[(index // 3) % len(LIGHTING)]
    floor = FLOORS[(index // 5) % len(FLOORS)]
    furniture = FURNITURE[(index // 7) % len(FURNITURE)]
    viewpoint = VIEWPOINTS[(index // 11) % len(VIEWPOINTS)]
    return (
        "Create one photorealistic, physically plausible photograph of an empty "
        f"{venue}. The room is {room_size}, with a {floor}, {lighting}, and is "
        f"{furniture}. Camera composition: {viewpoint}. Clearly show a main wall, "
        "floor-to-wall boundaries, one normal doorway, at least one window, ordinary "
        "furniture, one visible wall power outlet, and a clear possible walking path. "
        "Use realistic perspective, shadows, materials and architectural proportions. "
        "The space is undecorated and ready to be planned for an event. No people, no "
        "faces, no human reflections, no mannequins, no animals, no cake, no party "
        "decorations, no balloons, no flowers, no logos, no brands, no readable text, "
        "no signs, no watermarks, no posters, no framed artwork, no collage, no drawing, "
        "no floor plan and no computer-render appearance. Output a single room image."
    )


def _redact(value: str, secret: str) -> str:
    return value.replace(secret, "[REDACTED]") if secret else value


def _read_response(response, maximum_bytes: int = 30_000_000) -> bytes:
    payload = response.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise RuntimeError("Gemini response exceeded the 30 MB safety limit")
    return payload


def _request_generation(
    *,
    api_key: str,
    model: str,
    prompt: str,
    aspect_ratio: str,
    maximum_retries: int,
) -> dict:
    encoded_model = urllib.parse.quote(model, safe="-._")
    request_body = json.dumps(
        {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{API_ROOT}/{encoded_model}:generateContent",
        data=request_body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "x-goog-api-key": api_key,
        },
    )
    for attempt in range(maximum_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(_read_response(response))
        except urllib.error.HTTPError as exc:
            error_payload = _read_response(exc, maximum_bytes=1_000_000)
            error_text = _redact(error_payload.decode("utf-8", "replace"), api_key)
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt >= maximum_retries:
                raise RuntimeError(
                    f"Gemini API returned HTTP {exc.code}: {error_text[:500]}"
                ) from exc
            retry_after = exc.headers.get("Retry-After", "")
            delay = float(retry_after) if retry_after.isdigit() else 2.0 ** attempt
            time.sleep(min(max(delay, 1.0), 60.0))
        except (OSError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt >= maximum_retries:
                raise RuntimeError(
                    f"Gemini request failed: {_redact(str(exc), api_key)}"
                ) from exc
            time.sleep(min(2.0 ** attempt, 30.0))
    raise RuntimeError("unreachable")


def _extract_image(response: dict) -> tuple[bytes, str, str]:
    candidates = response.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini response contained no candidate")
    parts = candidates[0].get("content", {}).get("parts", [])
    response_texts: list[str] = []
    for part in parts:
        if isinstance(part.get("text"), str):
            response_texts.append(part["text"].strip())
        inline_data = part.get("inlineData") or part.get("inline_data")
        if not isinstance(inline_data, dict) or not inline_data.get("data"):
            continue
        mime_type = str(
            inline_data.get("mimeType") or inline_data.get("mime_type") or ""
        )
        if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise RuntimeError(f"Gemini returned unsupported image type: {mime_type}")
        try:
            payload = base64.b64decode(inline_data["data"], validate=True)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Gemini returned invalid base64 image data") from exc
        return payload, mime_type, " ".join(filter(None, response_texts))
    reason = " ".join(filter(None, response_texts))
    raise RuntimeError(f"Gemini response contained no image. Response text: {reason[:300]}")


def _normalise_image(payload: bytes) -> tuple[bytes, int, int]:
    try:
        with Image.open(io.BytesIO(payload)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            if min(image.size) < 512:
                raise RuntimeError("generated image is smaller than 512 pixels")
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue(), image.width, image.height
    except (OSError, ValueError) as exc:
        raise RuntimeError("Gemini returned an unreadable image") from exc


def _load_manifest(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MANIFEST_COLUMNS:
            raise ValueError("existing Gemini manifest has an unexpected schema")
        rows = list(reader)
    indexes = [row["prompt_index"] for row in rows]
    if len(indexes) != len(set(indexes)):
        raise ValueError("existing Gemini manifest has duplicate prompt indexes")
    for row in rows:
        image_path = (path.parent / row["image_path"]).resolve()
        if not image_path.is_file():
            raise ValueError(f"generated image is missing: {row['generation_id']}")
        checksum = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if checksum != row["image_sha256"]:
            raise ValueError(f"generated image checksum changed: {row['generation_id']}")
    return rows


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    temporary_path = path.with_suffix(".csv.part")
    with temporary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(path)


def generate_dataset(
    *,
    api_key: str,
    model: str,
    count: int,
    start_index: int,
    aspect_ratio: str,
    output_dir: Path,
    request_delay: float,
    maximum_retries: int,
) -> list[dict[str, str]]:
    if not api_key.strip():
        raise ValueError("GEMINI_API_KEY is missing or empty")
    if count < 1 or count > 1_000:
        raise ValueError("count must be between 1 and 1000")
    if start_index < 1:
        raise ValueError("start index must be at least 1")
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "generation_manifest.csv"
    rows = _load_manifest(manifest_path)
    completed_indexes = {int(row["prompt_index"]) for row in rows}

    for prompt_index in range(start_index, start_index + count):
        if prompt_index in completed_indexes:
            print(f"SKIP {prompt_index:04d}: already generated", flush=True)
            continue
        prompt = build_prompt(prompt_index)
        response = _request_generation(
            api_key=api_key,
            model=model,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            maximum_retries=maximum_retries,
        )
        source_payload, source_mime_type, response_text = _extract_image(response)
        image_payload, width, height = _normalise_image(source_payload)
        generation_id = f"gemini-venue-{prompt_index:04d}"
        image_path = images_dir / f"{generation_id}.jpg"
        temporary_image_path = image_path.with_suffix(".jpg.part")
        temporary_image_path.write_bytes(image_payload)
        temporary_image_path.replace(image_path)
        rows.append(
            {
                "generation_id": generation_id,
                "prompt_index": str(prompt_index),
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "model": model,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "provider": "Google Gemini API",
                "synthetic_status": "external_ai_generated",
                "training_status": "unlabelled_not_for_training",
                "prompt": prompt,
                "image_path": os.path.relpath(image_path, manifest_path.parent),
                "image_sha256": hashlib.sha256(image_payload).hexdigest(),
                "mime_type": f"{source_mime_type}; normalized=image/jpeg",
                "pixel_width": str(width),
                "pixel_height": str(height),
                "response_text": response_text,
            }
        )
        rows.sort(key=lambda row: int(row["prompt_index"]))
        _write_manifest(manifest_path, rows)
        completed_indexes.add(prompt_index)
        print(f"GENERATED {generation_id}: {width}x{height}", flush=True)
        if request_delay and prompt_index < start_index + count - 1:
            time.sleep(request_delay)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument(
        "--model", default=os.getenv("GEMINI_IMAGE_MODEL", DEFAULT_MODEL)
    )
    parser.add_argument("--aspect-ratio", default="16:9")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--request-delay", type=float, default=2.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--acknowledge-external-synthetic-data", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        for prompt_index in range(args.start_index, args.start_index + args.count):
            prompt = build_prompt(prompt_index)
            print(f"{prompt_index:04d} {hashlib.sha256(prompt.encode()).hexdigest()} {prompt}")
        return 0
    if not args.acknowledge_external_synthetic_data:
        print(
            "FAIL: pass --acknowledge-external-synthetic-data to confirm that these "
            "outputs are synthetic augmentation data, not real-photo evidence"
        )
        return 2
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    try:
        rows = generate_dataset(
            api_key=api_key,
            model=args.model,
            count=args.count,
            start_index=args.start_index,
            aspect_ratio=args.aspect_ratio,
            output_dir=args.output_dir,
            request_delay=max(args.request_delay, 0.0),
            maximum_retries=max(args.max_retries, 0),
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL: {_redact(str(exc), api_key)}")
        return 1
    print(
        f"PASS: manifest now contains {len(rows)} synthetic images; "
        "all remain unlabelled and blocked from training"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
