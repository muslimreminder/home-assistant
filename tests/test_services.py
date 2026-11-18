"""Actions and media source."""

from __future__ import annotations

from homeassistant.components import media_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.muslim_reminder.const import DOMAIN

CDN = "https://cdn.muslim-reminder.com/v1/sounds"


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    hass.states.async_set("media_player.salon", "idle", {"supported_features": 512})
    hass.states.async_set("media_player.cuisine", "idle", {"supported_features": 512})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("paris")
async def test_get_prayer_times(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await setup(hass, entry)
    response = await hass.services.async_call(
        DOMAIN, "get_prayer_times", {"date": "2026-11-18"}, blocking=True, return_response=True
    )
    assert response == {
        "date": "2026-11-18",
        "method": "FRANCE_18",
        "fajr": "2026-11-18T06:13:00+01:00",
        "sunrise": "2026-11-18T08:04:00+01:00",
        "dhuhr": "2026-11-18T12:36:00+01:00",
        "asr": "2026-11-18T14:45:00+01:00",
        "maghrib": "2026-11-18T17:07:00+01:00",
        "isha": "2026-11-18T18:58:00+01:00",
    }


@pytest.mark.usefixtures("paris")
async def test_play_actions(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await setup(hass, entry)
    play = async_mock_service(hass, "media_player", "play_media")

    await hass.services.async_call(
        DOMAIN, "play_salawat", {"entity_id": "media_player.cuisine", "sound": "reminder_3"}, blocking=True
    )
    assert play[-1].data["entity_id"] == "media_player.cuisine"
    assert play[-1].data["media_content_id"] == f"{CDN}/salawat/reminder_3.mp3"

    await hass.services.async_call(DOMAIN, "play_adhan", {"sound": "adhan_9", "full": False}, blocking=True)
    assert {c.data["media_content_id"] for c in play[1:]} == {f"{CDN}/adhan/adhan_9.mp3"}
    assert len(play) == 3


@pytest.mark.usefixtures("paris")
async def test_several_places_need_a_config_entry_id(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await setup(hass, entry)
    other = MockConfigEntry(domain=DOMAIN, title="Mosquée", data={"latitude": 45.76, "longitude": 4.83}, unique_id="x")
    other.add_to_hass(hass)
    assert await hass.config_entries.async_setup(other.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "get_prayer_times", {}, blocking=True, return_response=True)
    response = await hass.services.async_call(
        DOMAIN, "get_prayer_times", {"config_entry_id": other.entry_id}, blocking=True, return_response=True
    )
    assert response["method"] == "FRANCE_18"


@pytest.mark.usefixtures("paris")
async def test_media_source(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await setup(hass, entry)
    assert await async_setup_component(hass, "media_source", {})
    root = await media_source.async_browse_media(hass, f"media-source://{DOMAIN}")
    assert [child.title for child in root.children] == ["Salawat", "Adhan"]
    adhans = await media_source.async_browse_media(hass, f"media-source://{DOMAIN}/adhan")
    assert adhans.children[0].title == "Ahmad Al-Nufais"
    assert len(adhans.children) == 16  # 7 with a short version, 2 without
    resolved = await media_source.async_resolve_media(hass, f"media-source://{DOMAIN}/adhan/adhan_2/short", None)
    assert resolved.url == f"{CDN}/adhan/adhan_2.mp3"
    resolved = await media_source.async_resolve_media(hass, f"media-source://{DOMAIN}/adhan/adhan_2", None)
    assert resolved.url == f"{CDN}/adhan/adhan_2_full.mp3"
