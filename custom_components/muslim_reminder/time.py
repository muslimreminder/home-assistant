"""Times: start and end of the quiet hours of the salawat reminders."""

from __future__ import annotations

from contextlib import suppress
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import MuslimReminderConfigEntry
from .const import DEFAULT_QUIET_FROM, DEFAULT_QUIET_TO
from .entity import MuslimReminderEntity
from .manager import MuslimReminder

TIMES = (("quiet_from", DEFAULT_QUIET_FROM), ("quiet_to", DEFAULT_QUIET_TO))


async def async_setup_entry(
    hass: HomeAssistant, entry: MuslimReminderConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(QuietTime(entry.runtime_data, key, default) for key, default in TIMES)


class QuietTime(MuslimReminderEntity, TimeEntity, RestoreEntity):
    """A bound of the quiet hours (no salawat reminder in between)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, reminder: MuslimReminder, key: str, default: time) -> None:
        super().__init__(reminder, key)
        self._setting = key
        self._default = default

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        value = self._default
        if last:
            with suppress(ValueError):
                value = time.fromisoformat(last.state)
        self.reminder.set_setting(self._setting, value)
        await super().async_added_to_hass()

    @property
    def native_value(self) -> time:
        return getattr(self.reminder.settings, self._setting)

    async def async_set_value(self, value: time) -> None:
        self.reminder.set_setting(self._setting, value.replace(second=0, microsecond=0))
