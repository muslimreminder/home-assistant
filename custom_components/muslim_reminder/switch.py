"""Switches: salawat reminders, quiet hours, adhans.

Automations switch them on and off with the house (someone at home, a
baby asleep, the TV on…); they are restored after a restart.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import MuslimReminderConfigEntry
from .entity import MuslimReminderEntity
from .manager import MuslimReminder

# (translation key, setting, default as in the app)
SWITCHES = (
    ("salawat_reminders", "salawat_enabled", False),
    ("quiet_hours", "quiet_enabled", True),
    ("adhan", "adhan_enabled", True),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: MuslimReminderConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(ReminderSwitch(entry.runtime_data, *switch) for switch in SWITCHES)


class ReminderSwitch(MuslimReminderEntity, SwitchEntity, RestoreEntity):
    """A switch held by the integration."""

    def __init__(self, reminder: MuslimReminder, key: str, setting: str, default: bool) -> None:
        super().__init__(reminder, key)
        self._setting = setting
        self._default = default

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        value = last.state == STATE_ON if last and last.state in ("on", "off") else self._default
        self.reminder.set_setting(self._setting, value)
        await super().async_added_to_hass()

    @property
    def is_on(self) -> bool:
        return bool(getattr(self.reminder.settings, self._setting))

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.reminder.set_setting(self._setting, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.reminder.set_setting(self._setting, False)
