"""Sensors: the times of the day, the next prayer, the next salawat reminder."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MuslimReminderConfigEntry
from .const import METHODS, PRAYERS, TIMES
from .entity import MuslimReminderEntity
from .manager import MuslimReminder


async def async_setup_entry(
    hass: HomeAssistant, entry: MuslimReminderConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    reminder = entry.runtime_data
    async_add_entities(
        [
            *(PrayerTimeSensor(reminder, name) for name in TIMES),
            NextPrayerSensor(reminder),
            NextPrayerNameSensor(reminder),
            NextSalawatSensor(reminder),
            MethodSensor(reminder),
        ]
    )


class PrayerTimeSensor(MuslimReminderEntity, SensorEntity):
    """Today's time of a prayer (a timestamp: usable as a time trigger)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, reminder: MuslimReminder, name: str) -> None:
        super().__init__(reminder, name)
        self._name = name

    @property
    def native_value(self) -> datetime:
        return self.reminder.today()[self._name]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        tomorrow = self.reminder.times(dt_util.now().date() + timedelta(days=1))
        return {"tomorrow": dt_util.as_local(tomorrow[self._name]).isoformat()}


class NextPrayerSensor(MuslimReminderEntity, SensorEntity):
    """Time of the next of the five prayers."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, reminder: MuslimReminder) -> None:
        super().__init__(reminder, "next_prayer")

    @property
    def native_value(self) -> datetime:
        return self.reminder.next_time(dt_util.utcnow())[1]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"prayer": self.reminder.next_time(dt_util.utcnow())[0]}


class NextPrayerNameSensor(MuslimReminderEntity, SensorEntity):
    """Name of the next of the five prayers."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(PRAYERS)

    def __init__(self, reminder: MuslimReminder) -> None:
        super().__init__(reminder, "next_prayer_name")

    @property
    def native_value(self) -> str:
        return self.reminder.next_time(dt_util.utcnow())[0]


class NextSalawatSensor(MuslimReminderEntity, SensorEntity):
    """Time of the next salawat reminder (unknown when they are off)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, reminder: MuslimReminder) -> None:
        super().__init__(reminder, "next_salawat")

    @property
    def native_value(self) -> datetime | None:
        return self.reminder.next_salawat


class MethodSensor(MuslimReminderEntity, SensorEntity):
    """The calculation method in use (the automatic mode resolved by country)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = [key.lower() for key in METHODS]

    def __init__(self, reminder: MuslimReminder) -> None:
        super().__init__(reminder, "method")

    @property
    def native_value(self) -> str:
        return self.reminder.method.lower()
