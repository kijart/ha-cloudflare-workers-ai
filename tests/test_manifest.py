"""Tests for the integration manifest."""

import json
from pathlib import Path

from custom_components.cloudflare_workers_ai.const import DOMAIN

MANIFEST_PATH = (
    Path(__file__).parent.parent / "custom_components" / DOMAIN / "manifest.json"
)


def test_manifest_has_no_runtime_requirements() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["domain"] == DOMAIN == "cloudflare_workers_ai"
    assert manifest["name"] == "Cloudflare Workers AI"
    assert manifest["requirements"] == []
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "service"
