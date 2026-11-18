"""Events: a prayer time has come, a salawat reminder is due.

Automations trigger on them (or on the bus events muslim_reminder_prayer
and muslim_reminder_salawat, which carry the same data).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MuslimReminderConfigEntry
from .const import TIMES
from .entity import MuslimReminderEntity
from .manager import MuslimReminder


async def async_setup_entry(
    hass: HomeAssistant, entry: MuslimReminderConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    reminder = entry.runtime_data
    async_add_entities(
        [ReminderEvent(reminder, "prayer", list(TIMES)), ReminderEvent(reminder, "salawat", ["reminder"])]
    )


class ReminderEvent(MuslimReminderEntity, EventEntity):
    """Fired at each prayer time (event type = the prayer) or salawat reminder."""

    def __init__(self, reminder: MuslimReminder, key: str, event_types: list[str]) -> None:
        super().__init__(reminder, key)
        self._kind = key
        self._attr_event_types = event_types

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.reminder.async_add_event_listener(self._on_event))

    def _handle_update(self) -> None:
        """Nothing to show between two events."""

    @callback
    def _on_event(self, kind: str, event_type: str, data: dict[str, Any]) -> None:
        if kind == self._kind:
            self._trigger_event(event_type, data)
            self.async_write_ha_state()
