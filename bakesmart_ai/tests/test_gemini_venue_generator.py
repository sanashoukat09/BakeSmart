import base64
import csv
import hashlib
import io

from PIL import Image

from training.generate_gemini_venue_images import (
    MANIFEST_COLUMNS,
    _extract_image,
    _load_manifest,
    _normalise_image,
    _redact,
    build_prompt,
)


def _png_payload(size=(640, 512)):
    output = io.BytesIO()
    Image.new("RGB", size, (180, 170, 160)).save(output, format="PNG")
    return output.getvalue()


def test_prompts_are_deterministic_diverse_and_privacy_conservative():
    first = build_prompt(1)
    assert first == build_prompt(1)
    assert first != build_prompt(2)
    assert "No people" in first
    assert "no logos" in first
    assert "power outlet" in first


def test_extract_and_normalise_supported_inline_image():
    source = _png_payload()
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Generated venue."},
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64.b64encode(source).decode("ascii"),
                            }
                        },
                    ]
                }
            }
        ]
    }
    payload, mime_type, text = _extract_image(response)
    normalized, width, height = _normalise_image(payload)
    assert mime_type == "image/png"
    assert text == "Generated venue."
    assert (width, height) == (640, 512)
    assert normalized.startswith(b"\xff\xd8")


def test_manifest_loader_checks_stable_file_binding(tmp_path):
    image_path = tmp_path / "image.jpg"
    image_path.write_bytes(b"image")
    row = {column: "" for column in MANIFEST_COLUMNS}
    row.update(
        {
            "generation_id": "gemini-venue-0001",
            "prompt_index": "1",
            "image_path": "image.jpg",
            "image_sha256": hashlib.sha256(b"image").hexdigest(),
        }
    )
    manifest_path = tmp_path / "generation_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    assert _load_manifest(manifest_path) == [row]


def test_secret_redaction_never_echoes_api_key():
    assert _redact("request secret-key failed", "secret-key") == (
        "request [REDACTED] failed"
    )
