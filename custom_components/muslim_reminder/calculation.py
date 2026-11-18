"""Prayer times of a config entry, computed as the Muslim Reminder app does."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from . import adhan
from .const import (
    CONF_ADJUSTMENTS,
    CONF_FAJR_ANGLE,
    CONF_ISHA_ANGLE,
    CONF_MADHAB,
    CONF_MAGHRIB_ANGLE,
    CONF_METHOD,
    COUNTRY_TO_METHOD,
    FALLBACK_METHOD,
    LOGGER,
    MADHAB_HANAFI,
    METHOD_AUTO,
    METHODS,
    TIMES,
)


def effective_method(method: str | None, country: str | None) -> str:
    """Return the method key used, resolving the automatic mode by country.

    The automatic mode of the app picks the method of the country of the
    phone (`getAutomaticMethod`); here, the country of Home Assistant.
    """
    key = (method or METHOD_AUTO).upper()
    if key != METHOD_AUTO and key in METHODS:
        return key
    return COUNTRY_TO_METHOD.get((country or "").upper(), FALLBACK_METHOD)


def build_parameters(options: Mapping[str, Any], country: str | None) -> adhan.CalculationParameters:
    """Build the parameters as `computeMethodPrayerTimesObject` of the app.

    The method, the madhab (Hanafi, or Shafi for the three others), the
    minute adjustments, the custom angles, and the TwilightAngle rule the
    app always uses for high latitudes.
    """
    params = METHODS[effective_method(options.get(CONF_METHOD), country)]()
    params.madhab = adhan.HANAFI if options.get(CONF_MADHAB) == MADHAB_HANAFI else adhan.SHAFI
    adjustments = options.get(CONF_ADJUSTMENTS) or {}
    params.adjustments = {name: int(adjustments.get(name) or 0) for name in TIMES}
    if options.get(CONF_FAJR_ANGLE):
        params.fajr_angle = float(options[CONF_FAJR_ANGLE])
    if options.get(CONF_ISHA_ANGLE):
        params.isha_angle = float(options[CONF_ISHA_ANGLE])
    if options.get(CONF_MAGHRIB_ANGLE):
        params.maghrib_angle = float(options[CONF_MAGHRIB_ANGLE])
    params.high_latitude_rule = adhan.TWILIGHT_ANGLE
    return params


def times_for_day(
    day: date, latitude: float, longitude: float, params: adhan.CalculationParameters
) -> dict[str, datetime]:
    """Return the six times of a local day (UTC datetimes).

    Inside the polar circle, where the sun neither rises nor sets on some
    days, the app shows no time; a house still needs one, so the times of
    the nearest latitude where it does are used (AqrabBalad).
    """
    try:
        return adhan.prayer_times(day, latitude, longitude, params)
    except ValueError:
        LOGGER.debug("No sunrise or sunset on %s, using the nearest latitude", day)
        polar = adhan.CalculationParameters(**{**params.__dict__, "polar_circle_resolution": adhan.AQRAB_BALAD})
        return adhan.prayer_times(day, latitude, longitude, polar)
