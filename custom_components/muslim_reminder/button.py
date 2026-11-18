"""Buttons: try the sounds on the speakers, and stop them."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MuslimReminderConfigEntry
from .entity import MuslimReminderEntity
from .manager import MuslimReminder

BUTTONS: tuple[tuple[str, Callable[[MuslimReminder], Awaitable[Any]]], ...] = (
    ("play_salawat", lambda reminder: reminder.async_play_salawat()),
    ("play_adhan", lambda reminder: reminder.async_play_adhan(full=True)),
    ("stop", lambda reminder: reminder.async_stop_players()),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: MuslimReminderConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(ReminderButton(entry.runtime_data, key, action) for key, action in BUTTONS)


class ReminderButton(MuslimReminderEntity, ButtonEntity):
    """Plays (or stops) now, whatever the switches and the conditions."""

    def __init__(self, reminder: MuslimReminder, key: str, action: Callable[[MuslimReminder], Awaitable[Any]]) -> None:
        super().__init__(reminder, key)
        self._action = action

    async def async_press(self) -> None:
        await self._action(self.reminder)
