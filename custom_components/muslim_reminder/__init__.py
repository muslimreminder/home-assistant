"""Muslim Reminder for Home Assistant.

Prayer times computed as the Muslim Reminder app computes them, salawat
reminders (prayers upon the Prophet ﷺ) and adhans played on the speakers
of the house, switched on and off by the house itself.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .manager import MuslimReminder
from .services import async_setup_services

PLATFORMS = [
    Platform.BUTTON,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MuslimReminderConfigEntry = ConfigEntry[MuslimReminder]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions (play_salawat, play_adhan, get_prayer_times)."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MuslimReminderConfigEntry) -> bool:
    """Set up a place: compute its times, then start the timers.

    The timers start once the entities have restored the settings (switches,
    interval, quiet hours…), so that a restart never plays a reminder the
    house had switched off.
    """
    reminder = MuslimReminder(hass, entry)
    entry.runtime_data = reminder
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    reminder.async_start()
    entry.async_on_unload(reminder.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MuslimReminderConfigEntry) -> bool:
    """Unload a place."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: MuslimReminderConfigEntry) -> None:
    """New method, speakers or conditions: reload."""
    await hass.config_entries.async_reload(entry.entry_id)
