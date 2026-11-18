"""Selects: sounds, and what each prayer plays."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import MuslimReminderConfigEntry
from .const import (
    ADHAN_MODES,
    ADHAN_SOUNDS,
    DEFAULT_ADHAN_SOUND,
    DEFAULT_SALAWAT_SOUND,
    MODE_MUTE,
    PRAYERS,
    SALAWAT_SOUNDS,
)
from .entity import MuslimReminderEntity
from .manager import MuslimReminder


async def async_setup_entry(
    hass: HomeAssistant, entry: MuslimReminderConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    reminder = entry.runtime_data
    async_add_entities(
        [
            ReminderSelect(reminder, "salawat_sound", "salawat_sound", list(SALAWAT_SOUNDS), DEFAULT_SALAWAT_SOUND),
            ReminderSelect(reminder, "adhan_sound", "adhan_sound", list(ADHAN_SOUNDS), DEFAULT_ADHAN_SOUND),
            *(
                ReminderSelect(reminder, f"{prayer}_adhan", f"mode_{prayer}", list(ADHAN_MODES), MODE_MUTE)
                for prayer in PRAYERS
            ),
        ]
    )


class ReminderSelect(MuslimReminderEntity, SelectEntity, RestoreEntity):
    """A choice held by the integration."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, reminder: MuslimReminder, key: str, setting: str, options: list[str], default: str) -> None:
        super().__init__(reminder, key)
        self._setting = setting
        self._default = default
        self._attr_options = options

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        value = last.state if last and last.state in self.options else self._default
        self.reminder.set_setting(self._setting, value)
        await super().async_added_to_hass()

    @property
    def current_option(self) -> str:
        if self._setting.startswith("mode_"):
            return self.reminder.settings.modes[self._setting.removeprefix("mode_")]
        return getattr(self.reminder.settings, self._setting)

    async def async_select_option(self, option: str) -> None:
        self.reminder.set_setting(self._setting, option)
