"""The heart of the integration: prayer times, salawat reminders and adhans.

One `MuslimReminder` per config entry. It computes the prayer times of the
day, wakes up at each prayer and at each salawat reminder, fires the events
and plays the sounds on the media players of the options, when the switches
and the conditions allow it.

The entities hold the settings a house changes (switches, selects, numbers,
times) and push them here with `set_setting`; they restore them after a
restart. Everything else (location, method, speakers, conditions) lives in
the config entry.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import math
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    SERVICE_MEDIA_STOP,
    SERVICE_VOLUME_SET,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State, callback
from homeassistant.helpers.event import async_call_later, async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .calculation import build_parameters, effective_method, times_for_day
from .const import (
    ACTIVE_STATES,
    ADHAN_SOUNDS,
    CONF_ADHAN_BLOCKING,
    CONF_ADHAN_MEDIA,
    CONF_ADHAN_PLAYERS,
    CONF_ADHAN_REQUIRED,
    CONF_ANNOUNCE,
    CONF_METHOD,
    CONF_SALAWAT_BLOCKING,
    CONF_SALAWAT_MEDIA,
    CONF_SALAWAT_PLAYERS,
    CONF_SALAWAT_REQUIRED,
    CONF_SOUND_BASE_URL,
    DEFAULT_ADHAN_SOUND,
    DEFAULT_QUIET_FROM,
    DEFAULT_QUIET_TO,
    DEFAULT_SALAWAT_INTERVAL,
    DEFAULT_SALAWAT_SOUND,
    DEFAULT_SOUND_BASE_URL,
    EVENT_PRAYER,
    EVENT_SALAWAT,
    LOGGER,
    MODE_FULL,
    MODE_MUTE,
    PRAYERS,
    SALAWAT_SOUNDS,
    TIMES,
)

# How long to wait after a sound of unknown length before restoring the volume.
UNKNOWN_DURATION = 30.0
# Margin after the end of a sound before restoring the volume.
RESTORE_MARGIN = 3.0


@dataclass
class Settings:
    """The settings held by the entities, with the defaults of the app."""

    salawat_enabled: bool = False
    salawat_interval: int = DEFAULT_SALAWAT_INTERVAL
    quiet_enabled: bool = True
    quiet_from: time = DEFAULT_QUIET_FROM
    quiet_to: time = DEFAULT_QUIET_TO
    salawat_sound: str = DEFAULT_SALAWAT_SOUND
    salawat_volume: int = 0
    adhan_enabled: bool = True
    adhan_sound: str = DEFAULT_ADHAN_SOUND
    adhan_volume: int = 0
    modes: dict[str, str] = field(default_factory=lambda: dict.fromkeys(PRAYERS, MODE_MUTE))


def in_quiet_hours(moment: time, start: time, end: time) -> bool:
    """`isInSilenceTimes` of the app: strictly between, across midnight too."""
    if start < end:
        return start < moment < end
    return moment > start or moment < end


def salawat_slots(interval: int) -> list[time]:
    """Reminder times of a day: from 00:00, every `interval` minutes."""
    return [time(minute // 60, minute % 60) for minute in range(0, 24 * 60, max(1, interval))]


def is_active(state: State | None) -> bool:
    """Whether an entity counts as "active" for the conditions.

    on, home, open, playing… or a number above zero (zone.home holds the
    number of people at home).
    """
    if state is None:
        return False
    if state.state in ACTIVE_STATES:
        return True
    try:
        number = float(state.state)
    except ValueError:
        return False
    return math.isfinite(number) and number > 0


@dataclass
class Playback:
    """What to play and where."""

    players: list[str]
    url: str
    duration: float | None
    volume: int
    announce: bool


class MuslimReminder:
    """Prayer times, salawat reminders and adhans of a config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.settings = Settings()
        self._days: dict[date, dict[str, datetime]] = {}
        self._listeners: list[Callable[[], None]] = []
        self._event_listeners: list[Callable[[str, str, dict[str, Any]], None]] = []
        self._unsub_prayer: CALLBACK_TYPE | None = None
        self._unsub_salawat: CALLBACK_TYPE | None = None
        self._restores: list[CALLBACK_TYPE] = []
        self._started = False
        self.next_salawat: datetime | None = None
        self.last_salawat: datetime | None = None

    # --- Configuration ------------------------------------------------------

    @property
    def options(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    @property
    def latitude(self) -> float:
        return float(self.entry.data[CONF_LATITUDE])

    @property
    def longitude(self) -> float:
        return float(self.entry.data[CONF_LONGITUDE])

    @property
    def method(self) -> str:
        """The calculation method in use (the automatic mode resolved)."""
        return effective_method(self.options.get(CONF_METHOD), self.hass.config.country)

    # --- Prayer times -------------------------------------------------------

    def times(self, day: date) -> dict[str, datetime]:
        """The six times of a local day, cached."""
        if day not in self._days:
            params = build_parameters(self.options, self.hass.config.country)
            self._days[day] = times_for_day(day, self.latitude, self.longitude, params)
            for old in [d for d in self._days if d < day - timedelta(days=1)]:
                del self._days[old]
        return self._days[day]

    def today(self) -> dict[str, datetime]:
        return self.times(dt_util.now().date())

    def next_time(self, now: datetime, names: Iterable[str] = PRAYERS) -> tuple[str, datetime]:
        """The next of the given times strictly after `now`."""
        names = tuple(names)
        day = dt_util.as_local(now).date()
        for offset in range(3):
            times = self.times(day + timedelta(days=offset))
            upcoming = sorted((times[n], n) for n in names if times[n] > now)
            if upcoming:
                return upcoming[0][1], upcoming[0][0]
        raise RuntimeError("No prayer time in the next days")

    def current_prayer(self, now: datetime) -> str | None:
        """The prayer whose time has come and whose next one has not (None after midnight before Fajr)."""
        times = self.times(dt_util.as_local(now).date())
        passed = [n for n in TIMES if times[n] <= now]
        return passed[-1] if passed else None

    # --- Listeners ----------------------------------------------------------

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> CALLBACK_TYPE:
        """Call `update` when the times or the settings change."""
        self._listeners.append(update)
        return lambda: self._listeners.remove(update)

    @callback
    def async_add_event_listener(self, listener: Callable[[str, str, dict[str, Any]], None]) -> CALLBACK_TYPE:
        """Call `listener(kind, event_type, data)` at each prayer and reminder."""
        self._event_listeners.append(listener)
        return lambda: self._event_listeners.remove(listener)

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()

    @callback
    def set_setting(self, name: str, value: Any) -> None:
        """Change a setting (from an entity) and reschedule."""
        if name.startswith("mode_"):
            self.settings.modes[name.removeprefix("mode_")] = value
        else:
            setattr(self.settings, name, value)
        if self._started and name.startswith(("salawat", "quiet")):
            self._schedule_salawat()
        self._notify()

    # --- Scheduling ---------------------------------------------------------

    @callback
    def async_start(self) -> None:
        """Start the timers (once the entities have restored the settings)."""
        self._started = True
        self._schedule_prayer()
        self._schedule_salawat()
        self._notify()

    @callback
    def async_stop(self) -> None:
        self._started = False
        for unsub in (self._unsub_prayer, self._unsub_salawat, *self._restores):
            if unsub:
                unsub()
        self._unsub_prayer = self._unsub_salawat = None
        self._restores.clear()

    @callback
    def _schedule_prayer(self) -> None:
        if self._unsub_prayer:
            self._unsub_prayer()
        now = dt_util.utcnow()
        _, when = self.next_time(now, TIMES)
        # Also wake up at midnight: the sensors show the times of the new day.
        midnight = dt_util.as_utc(dt_util.start_of_local_day(dt_util.now() + timedelta(days=1)))
        self._unsub_prayer = async_track_point_in_utc_time(self.hass, self._on_prayer_timer, min(when, midnight))

    async def _on_prayer_timer(self, now: datetime) -> None:
        self._unsub_prayer = None
        times = self.times(dt_util.as_local(now).date())
        due = [n for n in TIMES if timedelta(0) <= now - times[n] < timedelta(minutes=1)]
        self._schedule_prayer()
        self._notify()
        for name in due:
            await self._prayer_time(name, times[name])

    def next_salawat_time(self, now: datetime) -> datetime | None:
        """The next salawat reminder after `now`, outside the quiet hours."""
        settings = self.settings
        if not settings.salawat_enabled:
            return None
        slots = [
            slot
            for slot in salawat_slots(settings.salawat_interval)
            if not settings.quiet_enabled or not in_quiet_hours(slot, settings.quiet_from, settings.quiet_to)
        ]
        if not slots:
            return None
        today = dt_util.as_local(now).date()
        for offset in range(2):
            day = today + timedelta(days=offset)
            for slot in slots:
                moment = dt_util.as_utc(datetime.combine(day, slot, tzinfo=dt_util.get_default_time_zone()))
                if moment > now:
                    return moment
        return None

    @callback
    def _schedule_salawat(self) -> None:
        if self._unsub_salawat:
            self._unsub_salawat()
            self._unsub_salawat = None
        self.next_salawat = self.next_salawat_time(dt_util.utcnow())
        if self.next_salawat:
            self._unsub_salawat = async_track_point_in_utc_time(self.hass, self._on_salawat_timer, self.next_salawat)

    async def _on_salawat_timer(self, now: datetime) -> None:
        self._unsub_salawat = None
        self.last_salawat = now
        self._schedule_salawat()
        self._notify()
        await self.async_salawat_reminder()

    # --- What happens ------------------------------------------------------

    def conditions_met(self, required_key: str, blocking_key: str) -> bool:
        """The conditions of the options: all "required" entities active, no "blocking" one."""
        options = self.options
        states = self.hass.states
        required = options.get(required_key) or []
        blocking = options.get(blocking_key) or []
        return all(is_active(states.get(e)) for e in required) and not any(is_active(states.get(e)) for e in blocking)

    async def _prayer_time(self, name: str, moment: datetime) -> None:
        played = False
        mode = self.settings.modes.get(name, MODE_MUTE) if name in PRAYERS else MODE_MUTE
        if (
            mode != MODE_MUTE
            and self.settings.adhan_enabled
            and self.conditions_met(CONF_ADHAN_REQUIRED, CONF_ADHAN_BLOCKING)
        ):
            played = await self.async_play_adhan(full=mode == MODE_FULL)
        data = {"prayer": name, "time": moment.isoformat(), "played": played}
        self._fire(EVENT_PRAYER, "prayer", name, data)

    async def async_salawat_reminder(self) -> None:
        """A salawat reminder is due: play it if the conditions allow it."""
        played = False
        if self.conditions_met(CONF_SALAWAT_REQUIRED, CONF_SALAWAT_BLOCKING):
            played = await self.async_play_salawat()
        self._fire(EVENT_SALAWAT, "salawat", "reminder", {"played": played})

    def _fire(self, event: str, kind: str, event_type: str, data: dict[str, Any]) -> None:
        self.hass.bus.async_fire(event, {"config_entry_id": self.entry.entry_id, **data})
        for listener in list(self._event_listeners):
            listener(kind, event_type, data)

    # --- Playback ----------------------------------------------------------

    def sound_url(self, file: str) -> str:
        base = (self.options.get(CONF_SOUND_BASE_URL) or DEFAULT_SOUND_BASE_URL).rstrip("/")
        return f"{base}/{file}"

    async def async_play_salawat(
        self, players: list[str] | None = None, sound: str | None = None, volume: int | None = None
    ) -> bool:
        """Play a salawat reminder; return whether a player was asked to."""
        custom = self.options.get(CONF_SALAWAT_MEDIA)
        if custom and sound is None:
            url, duration = custom, None
        else:
            chosen = SALAWAT_SOUNDS.get(sound or self.settings.salawat_sound) or SALAWAT_SOUNDS["reminder_2"]
            url, duration = self.sound_url(chosen.file), chosen.duration
        return await self._play(
            Playback(
                players if players is not None else list(self.options.get(CONF_SALAWAT_PLAYERS) or []),
                url,
                duration,
                self.settings.salawat_volume if volume is None else volume,
                bool(self.options.get(CONF_ANNOUNCE, True)),
            )
        )

    async def async_play_adhan(
        self,
        full: bool = True,
        players: list[str] | None = None,
        sound: str | None = None,
        volume: int | None = None,
    ) -> bool:
        """Play the adhan (full or short); return whether a player was asked to."""
        custom = self.options.get(CONF_ADHAN_MEDIA)
        if custom and sound is None:
            url, duration = custom, None
        else:
            chosen = ADHAN_SOUNDS.get(sound or self.settings.adhan_sound) or ADHAN_SOUNDS[DEFAULT_ADHAN_SOUND]
            if full and chosen.full_file:
                url, duration = self.sound_url(chosen.full_file), chosen.full_duration
            else:
                url, duration = self.sound_url(chosen.file), chosen.duration
        return await self._play(
            Playback(
                players if players is not None else list(self.options.get(CONF_ADHAN_PLAYERS) or []),
                url,
                duration,
                self.settings.adhan_volume if volume is None else volume,
                bool(self.options.get(CONF_ANNOUNCE, True)),
            )
        )

    async def async_stop_players(self) -> None:
        """Stop the configured players."""
        players = {*(self.options.get(CONF_SALAWAT_PLAYERS) or []), *(self.options.get(CONF_ADHAN_PLAYERS) or [])}
        if players:
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_STOP, {ATTR_ENTITY_ID: sorted(players)}, blocking=False
            )

    async def _resolve(self, media: str) -> str:
        """A media-source:// id becomes a URL the speakers can fetch."""
        if media_source.is_media_source_id(media):
            resolved = await media_source.async_resolve_media(self.hass, media, None)
            media = resolved.url
        return async_process_play_media_url(self.hass, media)

    async def _play(self, playback: Playback) -> bool:
        players = [p for p in playback.players if self._playable(self.hass.states.get(p))]
        if not players:
            LOGGER.debug("Nothing to play on: no available media player among %s", playback.players)
            return False
        try:
            url = await self._resolve(playback.url)
        except Exception:
            LOGGER.exception("Cannot resolve %s", playback.url)
            return False
        results = await asyncio.gather(*(self._play_on(p, url, playback) for p in players), return_exceptions=True)
        for player, result in zip(players, results, strict=True):
            if isinstance(result, Exception):
                LOGGER.warning("%s could not play %s: %s", player, url, result)
        return any(result is True for result in results)

    @staticmethod
    def _playable(state: State | None) -> bool:
        return state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, STATE_OFF)

    async def _play_on(self, player: str, url: str, playback: Playback) -> bool:
        state = self.hass.states.get(player)
        features = int(state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)) if state else 0
        announce = playback.announce and bool(features & MediaPlayerEntityFeature.MEDIA_ANNOUNCE)
        data: dict[str, Any] = {
            ATTR_ENTITY_ID: player,
            ATTR_MEDIA_CONTENT_ID: url,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
        }
        level = playback.volume / 100 if playback.volume else None
        if announce:
            # The player pauses what it plays, says the reminder and resumes.
            # The volume goes with the announcement (Sonos reads it there);
            # the volume of the music is left alone.
            data[ATTR_MEDIA_ANNOUNCE] = True
            if level is not None:
                data[ATTR_MEDIA_EXTRA] = {"volume": level}
        elif level is not None and features & MediaPlayerEntityFeature.VOLUME_SET:
            previous = state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) if state else None
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_VOLUME_SET,
                {ATTR_ENTITY_ID: player, ATTR_MEDIA_VOLUME_LEVEL: level},
                blocking=True,
            )
            if previous is not None and previous != level:
                self._restore_volume_later(player, float(previous), playback.duration)
        await self.hass.services.async_call(MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA, data, blocking=True)
        return True

    def _restore_volume_later(self, player: str, previous: float, duration: float | None) -> None:
        delay = (duration or UNKNOWN_DURATION) + RESTORE_MARGIN
        unsub: CALLBACK_TYPE | None = None

        async def restore(_: datetime) -> None:
            if unsub in self._restores:
                self._restores.remove(unsub)
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_VOLUME_SET,
                {ATTR_ENTITY_ID: player, ATTR_MEDIA_VOLUME_LEVEL: previous},
                blocking=False,
            )

        unsub = async_call_later(self.hass, delay, restore)
        self._restores.append(unsub)

    # --- Diagnostics / services --------------------------------------------

    def describe_day(self, day: date) -> dict[str, Any]:
        """The times of a day, for the get_prayer_times action."""
        times = self.times(day)
        return {
            "date": day.isoformat(),
            "method": self.method,
            **{name: dt_util.as_local(moment).isoformat() for name, moment in times.items()},
        }
