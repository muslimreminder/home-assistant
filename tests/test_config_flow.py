"""Config flow, reconfiguration and options."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.muslim_reminder.const import DEFAULT_SOUND_BASE_URL, DOMAIN


@pytest.mark.usefixtures("no_setup", "paris")
async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Maison", "location": {"latitude": 48.85, "longitude": 2.35}, "method": "auto", "madhab": "hanafi"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maison"
    assert result["data"] == {"latitude": 48.85, "longitude": 2.35}
    assert result["options"] == {"method": "auto", "madhab": "hanafi"}

    # The same place twice is refused.
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Encore", "location": {"latitude": 48.85, "longitude": 2.35}, "method": "auto", "madhab": "shafi"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("no_setup")
async def test_reconfigure(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Mosquée", "location": {"latitude": 45.76, "longitude": 4.83}}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Mosquée"
    assert entry.data == {"latitude": 45.76, "longitude": 4.83}
    assert entry.unique_id == "45.7600_4.8300"


@pytest.mark.usefixtures("no_setup")
async def test_options(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "speakers": {"salawat_players": ["media_player.salon"], "adhan_players": [], "announce": False},
            "conditions": {
                "salawat_required": ["zone.home"],
                "salawat_blocking": ["input_boolean.bebe_dort"],
                "adhan_required": [],
                "adhan_blocking": [],
            },
            "calculation": {
                "method": "umm_alqura",
                "madhab": "shafi",
                "adjust_fajr": 2,
                "adjust_sunrise": 0,
                "adjust_dhuhr": 0,
                "adjust_asr": 0,
                "adjust_maghrib": -1,
                "adjust_isha": 0,
                "fajr_angle": 17.5,
            },
            "sounds": {"sound_base_url": ""},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        "salawat_players": ["media_player.salon"],
        "adhan_players": [],
        "announce": False,
        "salawat_required": ["zone.home"],
        "salawat_blocking": ["input_boolean.bebe_dort"],
        "adhan_required": [],
        "adhan_blocking": [],
        "method": "umm_alqura",
        "madhab": "shafi",
        "fajr_angle": 17.5,
        "adjustments": {"fajr": 2, "sunrise": 0, "dhuhr": 0, "asr": 0, "maghrib": -1, "isha": 0},
        "sound_base_url": DEFAULT_SOUND_BASE_URL,
    }
