"""Actions: play_salawat, play_adhan, get_prayer_times."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_DATE, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import ADHAN_SOUNDS, DOMAIN, SALAWAT_SOUNDS

if TYPE_CHECKING:
    from .manager import MuslimReminder

ATTR_SOUND = "sound"
ATTR_VOLUME = "volume"
ATTR_FULL = "full"

_BASE = {
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_VOLUME): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
}

PLAY_SALAWAT_SCHEMA = vol.Schema({**_BASE, vol.Optional(ATTR_SOUND): vol.In(list(SALAWAT_SOUNDS))})
PLAY_ADHAN_SCHEMA = vol.Schema(
    {**_BASE, vol.Optional(ATTR_SOUND): vol.In(list(ADHAN_SOUNDS)), vol.Optional(ATTR_FULL, default=True): cv.boolean}
)
GET_TIMES_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string, vol.Optional(ATTR_DATE): cv.date})


def _reminder(hass: HomeAssistant, call: ServiceCall) -> MuslimReminder:
    """The place of the call: the given entry, or the only one."""
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_entry")
    if len(entries) > 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="several_entries")
    return entries[0].runtime_data


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions of the integration."""

    async def play_salawat(call: ServiceCall) -> None:
        await _reminder(hass, call).async_play_salawat(
            players=call.data.get(ATTR_ENTITY_ID), sound=call.data.get(ATTR_SOUND), volume=call.data.get(ATTR_VOLUME)
        )

    async def play_adhan(call: ServiceCall) -> None:
        await _reminder(hass, call).async_play_adhan(
            full=call.data[ATTR_FULL],
            players=call.data.get(ATTR_ENTITY_ID),
            sound=call.data.get(ATTR_SOUND),
            volume=call.data.get(ATTR_VOLUME),
        )

    async def get_prayer_times(call: ServiceCall) -> ServiceResponse:
        day: date = call.data.get(ATTR_DATE) or dt_util.now().date()
        return _reminder(hass, call).describe_day(day)

    hass.services.async_register(DOMAIN, "play_salawat", play_salawat, schema=PLAY_SALAWAT_SCHEMA)
    hass.services.async_register(DOMAIN, "play_adhan", play_adhan, schema=PLAY_ADHAN_SCHEMA)
    hass.services.async_register(
        DOMAIN, "get_prayer_times", get_prayer_times, schema=GET_TIMES_SCHEMA, supports_response=SupportsResponse.ONLY
    )
