"""Configuration: a place (its location), then its options."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_ADHAN_BLOCKING,
    CONF_ADHAN_MEDIA,
    CONF_ADHAN_PLAYERS,
    CONF_ADHAN_REQUIRED,
    CONF_ADJUSTMENTS,
    CONF_ANNOUNCE,
    CONF_FAJR_ANGLE,
    CONF_ISHA_ANGLE,
    CONF_MADHAB,
    CONF_MAGHRIB_ANGLE,
    CONF_METHOD,
    CONF_SALAWAT_BLOCKING,
    CONF_SALAWAT_MEDIA,
    CONF_SALAWAT_PLAYERS,
    CONF_SALAWAT_REQUIRED,
    CONF_SOUND_BASE_URL,
    DEFAULT_SOUND_BASE_URL,
    DOMAIN,
    MADHAB_SHAFI,
    MADHABS,
    METHOD_AUTO,
    METHODS,
    TIMES,
)

DEFAULT_NAME = "Muslim Reminder"

METHOD_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[key.lower() for key in (METHOD_AUTO, *METHODS)],
        translation_key="method",
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)
MADHAB_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=list(MADHABS), translation_key="madhab", mode=selector.SelectSelectorMode.LIST
    )
)
PLAYERS_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="media_player", multiple=True))
ENTITIES_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig(multiple=True))
MINUTES_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=-60, max=60, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min"
    )
)
ANGLE_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, max=30, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="°"
    )
)
TEXT_SELECTOR = selector.TextSelector()

SECTION_CALCULATION = "calculation"
SECTION_SPEAKERS = "speakers"
SECTION_CONDITIONS = "conditions"
SECTION_SOUNDS = "sounds"


def _location_schema(name: str, latitude: float, longitude: float) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=name): selector.TextSelector(),
            vol.Required(CONF_LOCATION, default={CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude}): (
                selector.LocationSelector(selector.LocationSelectorConfig(radius=False))
            ),
        }
    )


def _unique_id(latitude: float, longitude: float) -> str:
    return f"{latitude:.4f}_{longitude:.4f}"


class MuslimReminderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a place (a house, a mosque…): its location, method and madhab."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            latitude, longitude = float(location[CONF_LATITUDE]), float(location[CONF_LONGITUDE])
            await self.async_set_unique_id(_unique_id(latitude, longitude))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude},
                options={CONF_METHOD: user_input[CONF_METHOD], CONF_MADHAB: user_input[CONF_MADHAB]},
            )

        schema = _location_schema(DEFAULT_NAME, self.hass.config.latitude, self.hass.config.longitude).extend(
            {
                vol.Required(CONF_METHOD, default=METHOD_AUTO.lower()): METHOD_SELECTOR,
                vol.Required(CONF_MADHAB, default=MADHAB_SHAFI): MADHAB_SELECTOR,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Move the place (or rename it)."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            latitude, longitude = float(location[CONF_LATITUDE]), float(location[CONF_LONGITUDE])
            await self.async_set_unique_id(_unique_id(latitude, longitude))
            if self.unique_id != entry.unique_id:
                self._abort_if_unique_id_configured()
            return self.async_update_reload_and_abort(
                entry,
                unique_id=self.unique_id,
                title=user_input[CONF_NAME],
                data={CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude},
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_location_schema(entry.title, entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE]),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MuslimReminderOptionsFlow:
        return MuslimReminderOptionsFlow()


def _default(options: dict[str, Any], key: str) -> dict[str, Any]:
    """`suggested_value` only when there is one (a cleared field stays cleared)."""
    value = options.get(key)
    return {"suggested_value": value} if value not in (None, "", []) else {}


class MuslimReminderOptionsFlow(OptionsFlow):
    """Calculation, speakers, conditions and sounds of a place."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=self._flatten(user_input))

        options = dict(self.config_entry.options)
        adjustments = options.get(CONF_ADJUSTMENTS) or {}
        calculation = {
            vol.Required(CONF_METHOD, default=str(options.get(CONF_METHOD, METHOD_AUTO)).lower()): METHOD_SELECTOR,
            vol.Required(CONF_MADHAB, default=options.get(CONF_MADHAB, MADHAB_SHAFI)): MADHAB_SELECTOR,
            **{
                vol.Optional(f"adjust_{name}", default=int(adjustments.get(name) or 0)): MINUTES_SELECTOR
                for name in TIMES
            },
            vol.Optional(CONF_FAJR_ANGLE, description=_default(options, CONF_FAJR_ANGLE)): ANGLE_SELECTOR,
            vol.Optional(CONF_ISHA_ANGLE, description=_default(options, CONF_ISHA_ANGLE)): ANGLE_SELECTOR,
            vol.Optional(CONF_MAGHRIB_ANGLE, description=_default(options, CONF_MAGHRIB_ANGLE)): ANGLE_SELECTOR,
        }
        speakers = {
            vol.Optional(CONF_SALAWAT_PLAYERS, default=options.get(CONF_SALAWAT_PLAYERS, [])): PLAYERS_SELECTOR,
            vol.Optional(CONF_ADHAN_PLAYERS, default=options.get(CONF_ADHAN_PLAYERS, [])): PLAYERS_SELECTOR,
            vol.Optional(CONF_ANNOUNCE, default=options.get(CONF_ANNOUNCE, True)): selector.BooleanSelector(),
        }
        conditions = {
            vol.Optional(key, default=options.get(key, [])): ENTITIES_SELECTOR
            for key in (CONF_SALAWAT_REQUIRED, CONF_SALAWAT_BLOCKING, CONF_ADHAN_REQUIRED, CONF_ADHAN_BLOCKING)
        }
        sounds = {
            vol.Optional(CONF_SALAWAT_MEDIA, description=_default(options, CONF_SALAWAT_MEDIA)): TEXT_SELECTOR,
            vol.Optional(CONF_ADHAN_MEDIA, description=_default(options, CONF_ADHAN_MEDIA)): TEXT_SELECTOR,
            vol.Optional(
                CONF_SOUND_BASE_URL, default=options.get(CONF_SOUND_BASE_URL, DEFAULT_SOUND_BASE_URL)
            ): TEXT_SELECTOR,
        }
        schema = vol.Schema(
            {
                vol.Required(SECTION_SPEAKERS): section(vol.Schema(speakers), {"collapsed": False}),
                vol.Required(SECTION_CONDITIONS): section(vol.Schema(conditions), {"collapsed": True}),
                vol.Required(SECTION_CALCULATION): section(vol.Schema(calculation), {"collapsed": True}),
                vol.Required(SECTION_SOUNDS): section(vol.Schema(sounds), {"collapsed": True}),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    @staticmethod
    def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
        """Sections become flat options; the minute adjustments one dict."""
        flat: dict[str, Any] = {}
        for value in user_input.values():
            flat.update(value if isinstance(value, dict) else {})
        flat[CONF_ADJUSTMENTS] = {name: int(flat.pop(f"adjust_{name}", 0) or 0) for name in TIMES}
        if not flat.get(CONF_SOUND_BASE_URL):
            flat[CONF_SOUND_BASE_URL] = DEFAULT_SOUND_BASE_URL
        return {key: value for key, value in flat.items() if value not in (None, "")}
