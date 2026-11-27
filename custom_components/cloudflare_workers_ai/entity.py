"""Base entity for Cloudflare Workers AI."""

from datetime import date
import logging

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util

from . import CloudflareWorkersAIConfigEntry, CloudflareWorkersAIData
from .const import DOMAIN


class CloudflareWorkersAIEntity(Entity):
    """Base class of the Cloudflare Workers AI entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: CloudflareWorkersAIConfigEntry, key: str) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Cloudflare Workers AI",
            manufacturer="Cloudflare",
            entry_type=DeviceEntryType.SERVICE,
        )


def warn_quota_once(data: CloudflareWorkersAIData, logger: logging.Logger) -> None:
    """Log the exhausted daily quota once per UTC day."""
    today: date = dt_util.utcnow().date()
    if data.quota_warned_on == today:
        return
    data.quota_warned_on = today
    logger.warning(
        "Cloudflare Workers AI daily quota exhausted; requests fail until it resets"
    )
