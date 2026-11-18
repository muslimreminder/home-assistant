"""The blueprints load and do what they say."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

BLUEPRINTS = Path(__file__).parents[1] / "blueprints" / "automation" / "muslim_reminder"


@pytest.fixture
def blueprints(hass: HomeAssistant, tmp_path: Path) -> None:
    hass.config.config_dir = str(tmp_path)
    shutil.copytree(BLUEPRINTS, tmp_path / "blueprints" / "automation" / "muslim_reminder")


def automation(path: str, **inputs: object) -> dict:
    return {"use_blueprint": {"path": f"muslim_reminder/{path}", "input": inputs}}


def local(text: str) -> datetime:
    return dt_util.as_utc(datetime.fromisoformat(text).replace(tzinfo=dt_util.get_default_time_zone()))


@pytest.mark.usefixtures("blueprints", "paris")
async def test_prayer_time(hass: HomeAssistant) -> None:
    lights = async_mock_service(hass, "light", "turn_on")
    config = automation(
        "prayer_time.yaml",
        prayers=["maghrib"],
        actions=[{"action": "light.turn_on", "data": {"entity_id": "light.salon", "brightness": "{{ 10 }}"}}],
    )
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    hass.bus.async_fire("muslim_reminder_prayer", {"prayer": "asr"})
    await hass.async_block_till_done()
    assert not lights
    hass.bus.async_fire("muslim_reminder_prayer", {"prayer": "maghrib"})
    await hass.async_block_till_done()
    assert len(lights) == 1


@pytest.mark.usefixtures("blueprints", "paris")
async def test_before_prayer(hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(local("2026-11-18T03:00:00"))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    heaters = async_mock_service(hass, "climate", "turn_on")
    config = automation(
        "before_prayer.yaml",
        prayer_time="sensor.maison_fajr",
        offset={"hours": 0, "minutes": -30, "seconds": 0},
        actions=[{"action": "climate.turn_on", "target": {"entity_id": "climate.salle_de_bain"}}],
    )
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    await hass.async_block_till_done()

    for moment in ("2026-11-18T05:42:00", "2026-11-18T05:43:00"):  # Fajr is at 06:13
        freezer.move_to(local(moment))
        async_fire_time_changed(hass, local(moment))
        await hass.async_block_till_done()
    assert len(heaters) == 1


@pytest.mark.usefixtures("blueprints", "paris")
async def test_salawat_presence(hass: HomeAssistant) -> None:
    on = async_mock_service(hass, "switch", "turn_on")
    off = async_mock_service(hass, "switch", "turn_off")
    hass.states.async_set("zone.home", "0")
    config = automation("salawat_presence.yaml", reminders="switch.maison_salawat_reminders")
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    hass.states.async_set("zone.home", "2")
    await hass.async_block_till_done()
    assert on[-1].data["entity_id"] == ["switch.maison_salawat_reminders"]
    hass.states.async_set("zone.home", "0")
    await hass.async_block_till_done()
    assert len(off) == 1
