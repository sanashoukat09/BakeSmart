"""Repository guardrails for BakeSmart's local-only, from-scratch AI policy."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Mapping, Sequence


FORBIDDEN_PROVIDER_IMPORTS = (
    "openai",
    "anthropic",
    "google.generativeai",
    "google.genai",
    "roboflow",
    "replicate",
)

FORBIDDEN_PROVIDER_PACKAGES = (
    "openai",
    "anthropic",
    "google-generativeai",
    "google-genai",
    "roboflow",
    "replicate",
)

FORBIDDEN_PROVIDER_ENV_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "ROBOFLOW_API_KEY",
    "REPLICATE_API_TOKEN",
)

FORBIDDEN_INFERENCE_ENDPOINTS = (
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.roboflow.com",
    "api.replicate.com",
)

LEGACY_EXTERNAL_DATA_MARKERS = (
    "gemini_synthetic",
    "gemini-venue-",
)


def _matches_prefix(name: str, prefixes: Sequence[str]) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


def _python_import_violations(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        return [f"{path}: could not audit Python source: {exc}"]

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            if _matches_prefix(name, FORBIDDEN_PROVIDER_IMPORTS):
                violations.append(f"{path}: hosted AI provider import '{name}'")
    return violations


def assert_local_only_environment(environment: Mapping[str, str]) -> None:
    """Reject hosted-provider credentials before a local training/runtime task."""

    configured = [key for key in FORBIDDEN_PROVIDER_ENV_KEYS if environment.get(key)]
    if configured:
        raise RuntimeError(
            "Hosted AI provider credentials are not allowed for BakeSmart core AI: "
            + ", ".join(sorted(configured))
        )


def assert_training_paths_allowed(paths: Sequence[str | Path]) -> None:
    """Keep legacy externally generated synthetic material out of new model splits."""

    rejected: list[str] = []
    for value in paths:
        normalized = str(value).replace("\\", "/").lower()
        if any(marker in normalized for marker in LEGACY_EXTERNAL_DATA_MARKERS):
            rejected.append(str(value))
    if rejected:
        raise ValueError(
            "External synthetic material is excluded by the local-only training policy: "
            + ", ".join(rejected)
        )


def audit_repository(project_dir: Path) -> list[str]:
    """Return local-only policy violations in executable/configuration files."""

    root = project_dir.resolve()
    violations: list[str] = []

    requirements = root / "requirements.txt"
    if requirements.is_file():
        for raw_line in requirements.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip().lower()
            if not line or line.startswith("#"):
                continue
            package = line.split(";", 1)[0].strip()
            package = package.split("[", 1)[0]
            for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
                package = package.split(separator, 1)[0].strip()
            if package in FORBIDDEN_PROVIDER_PACKAGES:
                violations.append(
                    f"{requirements}: hosted AI provider dependency '{package}'"
                )

    env_example = root / ".env.example"
    if env_example.is_file():
        env_text = env_example.read_text(encoding="utf-8")
        for key in FORBIDDEN_PROVIDER_ENV_KEYS:
            if key in env_text:
                violations.append(f"{env_example}: hosted provider key '{key}'")

    for source_root_name in ("app", "training"):
        source_root = root / source_root_name
        if not source_root.is_dir():
            continue
        for path in source_root.rglob("*.py"):
            if path.name == "local_only_policy.py":
                continue
            violations.extend(_python_import_violations(path))
            try:
                text = path.read_text(encoding="utf-8").lower()
            except (OSError, UnicodeDecodeError) as exc:
                violations.append(f"{path}: could not audit endpoint text: {exc}")
                continue
            for endpoint in FORBIDDEN_INFERENCE_ENDPOINTS:
                if endpoint in text:
                    violations.append(
                        f"{path}: hosted AI inference endpoint '{endpoint}'"
                    )

    return violations
