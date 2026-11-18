"""Numbers: interval of the salawat reminders, volumes."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MuslimReminderConfigEntry
from .const import DEFAULT_SALAWAT_INTERVAL
from .entity import MuslimReminderEntity
from .manager import MuslimReminder

# (translation key, setting, min, max, step, unit, default)
NUMBERS = (
    # 5 to 60 minutes by 5, as in the app.
    ("salawat_interval", "salawat_interval", 5, 60, 5, UnitOfTime.MINUTES, DEFAULT_SALAWAT_INTERVAL),
    # 0 leaves the volume of the speakers as it is.
    ("salawat_volume", "salawat_volume", 0, 100, 5, PERCENTAGE, 0),
    ("adhan_volume", "adhan_volume", 0, 100, 5, PERCENTAGE, 0),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: MuslimReminderConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(ReminderNumber(entry.runtime_data, *number) for number in NUMBERS)


class ReminderNumber(MuslimReminderEntity, RestoreNumber):
    """A number held by the integration."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, reminder: MuslimReminder, key: str, setting: str, low: int, high: int, step: int, unit: str, default: int
    ) -> None:
        super().__init__(reminder, key)
        self._setting = setting
        self._default = default
        self._attr_native_min_value = low
        self._attr_native_max_value = high
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_number_data()
        value = self._default
        if last and last.native_value is not None:
            value = min(self.native_max_value, max(self.native_min_value, last.native_value))
        self.reminder.set_setting(self._setting, int(value))
        await super().async_added_to_hass()

    @property
    def native_value(self) -> float:
        return getattr(self.reminder.settings, self._setting)

    async def async_set_native_value(self, value: float) -> None:
        self.reminder.set_setting(self._setting, int(value))
