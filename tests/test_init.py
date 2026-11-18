"""Setup, entities, timers and playback."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
    mock_restore_cache,
)

from custom_components.muslim_reminder.const import (
    EVENT_PRAYER,
    EVENT_SALAWAT,
)
from custom_components.muslim_reminder.manager import in_quiet_hours, is_active, salawat_slots

CDN = "https://cdn.muslim-reminder.com/v1/sounds"
SPEAKER = MediaPlayerEntityFeature.PLAY_MEDIA | MediaPlayerEntityFeature.VOLUME_SET


def local(text: str) -> datetime:
    return dt_util.as_utc(datetime.fromisoformat(text).replace(tzinfo=dt_util.get_default_time_zone()))


async def setup(hass: HomeAssistant, entry: MockConfigEntry, **options: Any) -> dict[str, list[ServiceCall]]:
    """Set the place up, then mock the media_player actions.

    They are mocked after: setting the integration up sets media_player up,
    which registers the real actions.
    """
    entry.add_to_hass(hass)
    if options:
        hass.config_entries.async_update_entry(entry, options={**entry.options, **options})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return {
        service: async_mock_service(hass, "media_player", service)
        for service in ("play_media", "volume_set", "media_stop")
    }


def speakers(hass: HomeAssistant, features: int = SPEAKER, state: str = "idle", volume: float = 0.3) -> None:
    for player in ("media_player.salon", "media_player.cuisine"):
        hass.states.async_set(player, state, {"supported_features": int(features), "volume_level": volume})


async def at(hass: HomeAssistant, freezer: FrozenDateTimeFactory, moment: str) -> None:
    freezer.move_to(local(moment))
    async_fire_time_changed(hass, local(moment))
    await hass.async_block_till_done()


@pytest.mark.usefixtures("paris")
async def test_prayer_time_sensors(hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory) -> None:
    """Paris, automatic mode → France 18°: the times of the app (adhan-js gives 06:13 and 12:36)."""
    freezer.move_to(local("2026-11-18T10:00:00"))
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    assert hass.states.get("sensor.maison_calculation_method").state == "france_18"
    fajr = hass.states.get("sensor.maison_fajr")
    assert dt_util.parse_datetime(fajr.state) == local("2026-11-18T06:13:00")
    assert fajr.attributes["tomorrow"].startswith("2026-11-19T06:")
    assert dt_util.parse_datetime(hass.states.get("sensor.maison_dhuhr").state) == local("2026-11-18T12:36:00")
    assert hass.states.get("sensor.maison_next_prayer_name").state == "dhuhr"
    assert hass.states.get("sensor.maison_next_prayer").attributes["prayer"] == "dhuhr"
    assert hass.states.get("sensor.maison_next_salawat_reminder").state == "unknown"

    # After Isha, the next prayer is tomorrow's Fajr; at midnight, the times change.
    await at(hass, freezer, "2026-11-18T22:00:00")
    assert hass.states.get("sensor.maison_next_prayer_name").state == "fajr"
    await at(hass, freezer, "2026-11-19T00:00:01")
    assert dt_util.parse_datetime(hass.states.get("sensor.maison_fajr").state).date().isoformat() == "2026-11-19"


@pytest.mark.usefixtures("paris")
async def test_adhan_at_prayer_time(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local("2026-11-18T12:00:00"))
    speakers(hass)
    events = async_capture_events(hass, EVENT_PRAYER)
    calls = await setup(hass, entry)

    # Dhuhr is silent by default (as in the app): the event fires, nothing plays.
    await at(hass, freezer, "2026-11-18T12:36:00")
    assert [e.data["prayer"] for e in events] == ["dhuhr"]
    assert events[0].data["played"] is False
    assert not calls["play_media"]
    assert hass.states.get("event.maison_prayer_time").attributes["event_type"] == "dhuhr"

    # Full adhan for Asr, at 60 % on the two speakers, then the volume comes back.
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.maison_asr_adhan", "option": "full"}, blocking=True
    )
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.maison_adhan_volume", "value": 60}, blocking=True
    )
    asr = dt_util.parse_datetime(hass.states.get("sensor.maison_asr").state)
    await at(hass, freezer, dt_util.as_local(asr).replace(tzinfo=None).isoformat())
    assert events[-1].data == {
        "config_entry_id": entry.entry_id,
        "prayer": "asr",
        "time": asr.isoformat(),
        "played": True,
    }
    assert sorted(c.data["entity_id"] for c in calls["play_media"]) == ["media_player.cuisine", "media_player.salon"]
    assert calls["play_media"][0].data["media_content_id"] == f"{CDN}/adhan/adhan_1_full.mp3"
    assert {c.data["volume_level"] for c in calls["volume_set"]} == {0.6}

    await at(hass, freezer, (dt_util.as_local(asr).replace(tzinfo=None) + timedelta(seconds=220)).isoformat())
    assert [c.data["volume_level"] for c in calls["volume_set"][2:]] == [0.3, 0.3]


@pytest.mark.usefixtures("paris")
async def test_adhan_switch_and_blocking_entity(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    options = dict(adhan_blocking=["media_player.tv"])
    freezer.move_to(local("2026-11-18T12:00:00"))
    speakers(hass)
    hass.states.async_set("media_player.tv", "playing")
    calls = await setup(hass, entry, **options)
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.maison_dhuhr_adhan", "option": "short"}, blocking=True
    )

    # The TV is playing: no adhan.
    await at(hass, freezer, "2026-11-18T12:36:00")
    assert not calls["play_media"]

    # The TV is off, but the adhan switch is off too.
    hass.states.async_set("media_player.tv", "off")
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.maison_asr_adhan", "option": "short"}, blocking=True
    )
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.maison_adhan"}, blocking=True)
    asr = dt_util.as_local(dt_util.parse_datetime(hass.states.get("sensor.maison_asr").state)).replace(tzinfo=None)
    await at(hass, freezer, asr.isoformat())
    assert not calls["play_media"]

    # Short adhan at Maghrib.
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.maison_adhan"}, blocking=True)
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.maison_maghrib_adhan", "option": "short"}, blocking=True
    )
    maghrib = dt_util.as_local(dt_util.parse_datetime(hass.states.get("sensor.maison_maghrib").state)).replace(
        tzinfo=None
    )
    await at(hass, freezer, maghrib.isoformat())
    assert {c.data["media_content_id"] for c in calls["play_media"]} == {f"{CDN}/adhan/adhan_1.mp3"}


@pytest.mark.usefixtures("paris")
async def test_salawat_reminders(hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(local("2026-11-18T10:01:00"))
    speakers(hass, features=SPEAKER | MediaPlayerEntityFeature.MEDIA_ANNOUNCE)
    events = async_capture_events(hass, EVENT_SALAWAT)
    calls = await setup(hass, entry)

    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.maison_salawat_reminders"}, blocking=True)
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.maison_salawat_interval", "value": 20}, blocking=True
    )
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.maison_salawat_volume", "value": 40}, blocking=True
    )
    assert dt_util.parse_datetime(hass.states.get("sensor.maison_next_salawat_reminder").state) == local(
        "2026-11-18T10:20:00"
    )

    await at(hass, freezer, "2026-11-18T10:20:00")
    assert len(events) == 1 and events[0].data["played"] is True
    # An announcement: the music resumes after, its volume is left alone.
    assert calls["play_media"][0].data == {
        "entity_id": "media_player.salon",
        "media_content_id": f"{CDN}/salawat/reminder_2.mp3",
        "media_content_type": "music",
        "announce": True,
        "extra": {"volume": 0.4},
    }
    assert not calls["volume_set"]
    assert hass.states.get("event.maison_salawat_reminder").attributes["event_type"] == "reminder"
    assert dt_util.parse_datetime(hass.states.get("sensor.maison_next_salawat_reminder").state) == local(
        "2026-11-18T10:40:00"
    )

    # Quiet hours (23:30 → 09:30 by default): the 23:40 … 09:20 reminders are skipped.
    await at(hass, freezer, "2026-11-18T23:20:00")
    assert dt_util.parse_datetime(hass.states.get("sensor.maison_next_salawat_reminder").state) == local(
        "2026-11-19T09:40:00"
    )

    # Without quiet hours, the night is not skipped.
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.maison_quiet_hours"}, blocking=True)
    assert dt_util.parse_datetime(hass.states.get("sensor.maison_next_salawat_reminder").state) == local(
        "2026-11-18T23:40:00"
    )
    await hass.services.async_call(
        "time", "set_value", {"entity_id": "time.maison_quiet_hours_end", "time": "07:00"}, blocking=True
    )
    assert hass.states.get("time.maison_quiet_hours_end").state == "07:00:00"


@pytest.mark.usefixtures("paris")
async def test_salawat_only_when_someone_is_home(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    options = dict(salawat_required=["zone.home"], announce=False)
    freezer.move_to(local("2026-11-18T10:01:00"))
    speakers(hass)
    hass.states.async_set("zone.home", "0")
    events = async_capture_events(hass, EVENT_SALAWAT)
    calls = await setup(hass, entry, **options)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.maison_salawat_reminders"}, blocking=True)

    await at(hass, freezer, "2026-11-18T10:25:00")
    assert events[-1].data["played"] is False
    assert not calls["play_media"]

    hass.states.async_set("zone.home", "2")
    await at(hass, freezer, "2026-11-18T10:50:00")
    assert events[-1].data["played"] is True
    assert "announce" not in calls["play_media"][0].data


@pytest.mark.usefixtures("paris")
async def test_unavailable_or_off_speakers_are_skipped(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    speakers(hass, state="off")
    calls = await setup(hass, entry)
    await hass.services.async_call("button", "press", {"entity_id": "button.maison_play_the_adhan"}, blocking=True)
    assert not calls["play_media"]


@pytest.mark.usefixtures("paris")
async def test_custom_sound_from_the_media_browser(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    options = dict(salawat_media="media-source://muslim_reminder/salawat/reminder_6")
    speakers(hass)
    calls = await setup(hass, entry, **options)
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.maison_play_a_salawat_reminder"}, blocking=True
    )
    assert calls["play_media"][0].data["media_content_id"] == f"{CDN}/salawat/reminder_6.mp3"
    await hass.services.async_call("button", "press", {"entity_id": "button.maison_stop_the_speakers"}, blocking=True)
    assert calls["media_stop"][0].data["entity_id"] == ["media_player.cuisine", "media_player.salon"]


@pytest.mark.usefixtures("paris")
async def test_settings_are_restored(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local("2026-11-18T10:01:00"))
    mock_restore_cache(
        hass,
        [
            State("switch.maison_salawat_reminders", "on"),
            State("select.maison_salawat_sound", "reminder_5"),
            State("select.maison_fajr_adhan", "full"),
            State("time.maison_quiet_hours_start", "22:00:00"),
        ],
    )
    await setup(hass, entry)
    reminder = entry.runtime_data
    assert reminder.settings.salawat_enabled is True
    assert reminder.settings.salawat_sound == "reminder_5"
    assert reminder.settings.modes["fajr"] == "full"
    assert reminder.settings.quiet_from == time(22, 0)
    assert hass.states.get("sensor.maison_next_salawat_reminder").state != "unknown"


@pytest.mark.usefixtures("paris")
async def test_unload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


def test_salawat_slots_every_interval() -> None:
    """From 00:00 every n minutes (the app resets to :00 each hour when n does not divide 60)."""
    assert salawat_slots(25)[:4] == [time(0, 0), time(0, 25), time(0, 50), time(1, 15)]
    assert len(salawat_slots(25)) == 58
    assert len(salawat_slots(60)) == 24


@pytest.mark.parametrize(
    ("moment", "start", "end", "quiet"),
    [
        (time(23, 40), time(23, 30), time(9, 30), True),
        (time(3, 0), time(23, 30), time(9, 30), True),
        (time(9, 30), time(23, 30), time(9, 30), False),
        (time(12, 0), time(23, 30), time(9, 30), False),
        (time(13, 0), time(12, 0), time(14, 0), True),
        (time(12, 0), time(12, 0), time(14, 0), False),
    ],
)
def test_quiet_hours(moment: time, start: time, end: time, quiet: bool) -> None:
    assert in_quiet_hours(moment, start, end) is quiet


@pytest.mark.parametrize(
    ("state", "active"),
    [
        ("on", True),
        ("home", True),
        ("playing", True),
        ("off", False),
        ("not_home", False),
        ("2", True),
        ("0", False),
        ("unavailable", False),
    ],
)
def test_active_states(state: str, active: bool) -> None:
    assert is_active(State("sensor.x", state)) is active
    assert is_active(None) is False


@pytest.mark.usefixtures("paris")
async def test_names_follow_the_language(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """The ids come from the translated names, as the README says."""
    hass.config.language = "fr"
    await setup(hass, entry)
    assert hass.states.get("switch.maison_rappels_de_salawat").name == "Maison Rappels de salawat"
    assert hass.states.get("sensor.maison_prochaine_priere") is not None
    assert hass.states.get("sensor.maison_lever_du_soleil") is not None
    assert hass.states.get("select.maison_adhan_de_fajr").state == "mute"
