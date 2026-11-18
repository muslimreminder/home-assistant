"""Prayer time calculation, ported line for line from adhan-js 4.4.3.

The Muslim Reminder app computes its prayer times with adhan-js
(https://github.com/batoulapps/adhan-js, MIT License, Copyright (c) 2016
Batoul Apps). Porting the same algorithm, with the same constants and the
same rounding, keeps the times shown by Home Assistant identical to the
ones of the app, to the minute. `tests/fixtures/adhan_reference.json` is
generated with adhan-js itself and the test suite checks every time.

Only what the app uses is ported: the prayer times, the calculation
methods, the madhabs, the high latitude rules and the polar circle
resolutions. No external dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
import math

PRAYERS = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")

# Madhabs (Asr shadow length).
SHAFI = "shafi"
HANAFI = "hanafi"

# High latitude rules.
MIDDLE_OF_THE_NIGHT = "middleofthenight"
SEVENTH_OF_THE_NIGHT = "seventhofthenight"
TWILIGHT_ANGLE = "twilightangle"

# Polar circle resolutions.
AQRAB_BALAD = "AqrabBalad"
AQRAB_YAUM = "AqrabYaum"
UNRESOLVED = "Unresolved"

# Rounding of the seconds.
NEAREST = "nearest"
UP = "up"
NONE = "none"

# Shafaq (only used by the Moonsighting Committee method).
GENERAL = "general"
AHMER = "ahmer"
ABYAD = "abyad"


def _zero() -> dict[str, float]:
    return dict.fromkeys(PRAYERS, 0)


@dataclass
class CalculationParameters:
    """Parameters of a calculation, as `CalculationParameters` in adhan-js."""

    method: str = "Other"
    fajr_angle: float = 0
    isha_angle: float = 0
    isha_interval: float = 0
    maghrib_angle: float = 0
    madhab: str = SHAFI
    high_latitude_rule: str = MIDDLE_OF_THE_NIGHT
    adjustments: dict[str, float] = field(default_factory=_zero)
    method_adjustments: dict[str, float] = field(default_factory=_zero)
    polar_circle_resolution: str = UNRESOLVED
    rounding: str = NEAREST
    shafaq: str = GENERAL

    def night_portions(self) -> tuple[float, float]:
        """Return the (fajr, isha) portions of the night."""
        if self.high_latitude_rule == MIDDLE_OF_THE_NIGHT:
            return 1 / 2, 1 / 2
        if self.high_latitude_rule == SEVENTH_OF_THE_NIGHT:
            return 1 / 7, 1 / 7
        if self.high_latitude_rule == TWILIGHT_ANGLE:
            return self.fajr_angle / 60, self.isha_angle / 60
        raise ValueError(f"Invalid high latitude rule: {self.high_latitude_rule}")


def _method(
    name: str, fajr: float, isha: float, interval: float = 0, maghrib_angle: float = 0, **adjustments: float
) -> CalculationParameters:
    params = CalculationParameters(name, fajr, isha, interval, maghrib_angle)
    params.method_adjustments.update(adjustments)
    return params


# Calculation methods of adhan-js, under the same names.
METHODS = {
    "MuslimWorldLeague": lambda: _method("MuslimWorldLeague", 18, 17, dhuhr=1),
    "Egyptian": lambda: _method("Egyptian", 19.5, 17.5, dhuhr=1),
    "Karachi": lambda: _method("Karachi", 18, 18, dhuhr=1),
    "UmmAlQura": lambda: _method("UmmAlQura", 18.5, 0, 90),
    "Dubai": lambda: _method("Dubai", 18.2, 18.2, sunrise=-3, dhuhr=3, asr=3, maghrib=3),
    "MoonsightingCommittee": lambda: _method("MoonsightingCommittee", 18, 18, dhuhr=5, maghrib=3),
    "NorthAmerica": lambda: _method("NorthAmerica", 15, 15, dhuhr=1),
    "Kuwait": lambda: _method("Kuwait", 18, 17.5),
    "Qatar": lambda: _method("Qatar", 18, 0, 90),
    "Singapore": lambda: replace(_method("Singapore", 20, 18, dhuhr=1), rounding=UP),
    "Tehran": lambda: _method("Tehran", 17.7, 14, 0, 4.5),
    "Turkey": lambda: _method("Turkey", 18, 17, sunrise=-7, dhuhr=5, asr=4, maghrib=7),
    "Other": lambda: _method("Other", 0, 0),
}


def calculation_method(name: str) -> CalculationParameters:
    """Return fresh parameters for an adhan-js calculation method."""
    return METHODS[name]()


def recommended_high_latitude_rule(latitude: float) -> str:
    """Return `HighLatitudeRule.recommended` of adhan-js."""
    return SEVENTH_OF_THE_NIGHT if latitude > 48 else MIDDLE_OF_THE_NIGHT


# --- MathUtils -------------------------------------------------------------


def _rad(degrees: float) -> float:
    return degrees * math.pi / 180.0


def _deg(radians: float) -> float:
    return radians * 180.0 / math.pi


def _normalize(num: float, maximum: float) -> float:
    return num - maximum * math.floor(num / maximum)


def _unwind(angle: float) -> float:
    return _normalize(angle, 360.0)


def _js_round(value: float) -> float:
    """Math.round of JavaScript (halves go up, unlike Python's round)."""
    return math.floor(value + 0.5)


def _quadrant_shift(angle: float) -> float:
    if -180 <= angle <= 180:
        return angle
    return angle - 360 * _js_round(angle / 360)


def _acos(value: float) -> float:
    # Math.acos returns NaN out of [-1, 1]; Python raises.
    if value < -1 or value > 1 or math.isnan(value):
        return math.nan
    return math.acos(value)


# --- Astronomical ----------------------------------------------------------


def _mean_solar_longitude(t: float) -> float:
    return _unwind(280.4664567 + 36000.76983 * t + 0.0003032 * t**2)


def _mean_lunar_longitude(t: float) -> float:
    return _unwind(218.3165 + 481267.8813 * t)


def _ascending_lunar_node_longitude(t: float) -> float:
    return _unwind(125.04452 - 1934.136261 * t + 0.0020708 * t**2 + t**3 / 450000)


def _mean_solar_anomaly(t: float) -> float:
    return _unwind(357.52911 + 35999.05029 * t - 0.0001537 * t**2)


def _solar_equation_of_the_center(t: float, mean_anomaly: float) -> float:
    m = _rad(mean_anomaly)
    term1 = (1.914602 - 0.004817 * t - 0.000014 * t**2) * math.sin(m)
    term2 = (0.019993 - 0.000101 * t) * math.sin(2 * m)
    term3 = 0.000289 * math.sin(3 * m)
    return term1 + term2 + term3


def _apparent_solar_longitude(t: float, mean_longitude: float) -> float:
    longitude = mean_longitude + _solar_equation_of_the_center(t, _mean_solar_anomaly(t))
    omega = 125.04 - 1934.136 * t
    return _unwind(longitude - 0.00569 - 0.00478 * math.sin(_rad(omega)))


def _mean_obliquity_of_the_ecliptic(t: float) -> float:
    return 23.439291 - 0.013004167 * t - 0.0000001639 * t**2 + 0.0000005036 * t**3


def _apparent_obliquity_of_the_ecliptic(t: float, mean_obliquity: float) -> float:
    o = 125.04 - 1934.136 * t
    return mean_obliquity + 0.00256 * math.cos(_rad(o))


def _mean_sidereal_time(t: float) -> float:
    jd = t * 36525 + 2451545.0
    theta = 280.46061837 + 360.98564736629 * (jd - 2451545) + 0.000387933 * t**2 - t**3 / 38710000
    return _unwind(theta)


def _nutation_in_longitude(l0: float, lp: float, omega: float) -> float:
    return (
        -17.2 / 3600 * math.sin(_rad(omega))
        - 1.32 / 3600 * math.sin(2 * _rad(l0))
        - 0.23 / 3600 * math.sin(2 * _rad(lp))
        + 0.21 / 3600 * math.sin(2 * _rad(omega))
    )


def _nutation_in_obliquity(l0: float, lp: float, omega: float) -> float:
    return (
        9.2 / 3600 * math.cos(_rad(omega))
        + 0.57 / 3600 * math.cos(2 * _rad(l0))
        + 0.1 / 3600 * math.cos(2 * _rad(lp))
        - 0.09 / 3600 * math.cos(2 * _rad(omega))
    )


def _altitude_of_celestial_body(latitude: float, declination: float, hour_angle: float) -> float:
    term1 = math.sin(_rad(latitude)) * math.sin(_rad(declination))
    term2 = math.cos(_rad(latitude)) * math.cos(_rad(declination)) * math.cos(_rad(hour_angle))
    value = term1 + term2
    if value < -1 or value > 1 or math.isnan(value):
        return math.nan
    return _deg(math.asin(value))


def _approximate_transit(longitude: float, sidereal_time: float, right_ascension: float) -> float:
    return _normalize((right_ascension - longitude - sidereal_time) / 360, 1)


def _interpolate(y2: float, y1: float, y3: float, n: float) -> float:
    a = y2 - y1
    b = y3 - y2
    c = b - a
    return y2 + n / 2 * (a + b + n * c)


def _interpolate_angles(y2: float, y1: float, y3: float, n: float) -> float:
    a = _unwind(y2 - y1)
    b = _unwind(y3 - y2)
    c = b - a
    return y2 + n / 2 * (a + b + n * c)


def _julian_day(year: int, month: int, day: int, hours: float = 0) -> float:
    y = year if month > 2 else year - 1
    m = month if month > 2 else month + 12
    d = day + hours / 24
    a = math.trunc(y / 100)
    b = math.trunc(2 - a + math.trunc(a / 4))
    i0 = math.trunc(365.25 * (y + 4716))
    i1 = math.trunc(30.6001 * (m + 1))
    return i0 + i1 + d + b - 1524.5


def _is_leap_year(year: int) -> bool:
    if year % 4 != 0:
        return False
    return not (year % 100 == 0 and year % 400 != 0)


def _days_since_solstice(day_of_year: int, year: int, latitude: float) -> int:
    days_in_year = 366 if _is_leap_year(year) else 365
    if latitude >= 0:
        days = day_of_year + 10
        if days >= days_in_year:
            days -= days_in_year
    else:
        days = day_of_year - (173 if _is_leap_year(year) else 172)
        if days < 0:
            days += days_in_year
    return days


def _season_adjustment(dyy: int, a: float, b: float, c: float, d: float) -> float:
    if dyy < 91:
        return a + (b - a) / 91.0 * dyy
    if dyy < 137:
        return b + (c - b) / 46.0 * (dyy - 91)
    if dyy < 183:
        return c + (d - c) / 46.0 * (dyy - 137)
    if dyy < 229:
        return d + (c - d) / 46.0 * (dyy - 183)
    if dyy < 275:
        return c + (b - c) / 46.0 * (dyy - 229)
    return b + (a - b) / 91.0 * (dyy - 275)


def _season_adjusted_morning_twilight(latitude: float, day_of_year: int, year: int, sunrise: datetime) -> datetime:
    lat = abs(latitude)
    adjustment = _season_adjustment(
        _days_since_solstice(day_of_year, year, latitude),
        75 + 28.65 / 55.0 * lat,
        75 + 19.44 / 55.0 * lat,
        75 + 32.74 / 55.0 * lat,
        75 + 48.1 / 55.0 * lat,
    )
    return sunrise + timedelta(seconds=_js_round(adjustment * -60.0))


def _season_adjusted_evening_twilight(
    latitude: float, day_of_year: int, year: int, sunset: datetime, shafaq: str
) -> datetime:
    lat = abs(latitude)
    if shafaq == AHMER:
        abcd = (62 + 17.4 / 55.0 * lat, 62 - 7.16 / 55.0 * lat, 62 + 5.12 / 55.0 * lat, 62 + 19.44 / 55.0 * lat)
    elif shafaq == ABYAD:
        abcd = (75 + 25.6 / 55.0 * lat, 75 + 7.16 / 55.0 * lat, 75 + 36.84 / 55.0 * lat, 75 + 81.84 / 55.0 * lat)
    else:
        abcd = (75 + 25.6 / 55.0 * lat, 75 + 2.05 / 55.0 * lat, 75 - 9.21 / 55.0 * lat, 75 + 6.14 / 55.0 * lat)
    adjustment = _season_adjustment(_days_since_solstice(day_of_year, year, latitude), *abcd)
    return sunset + timedelta(seconds=_js_round(adjustment * 60.0))


# --- SolarCoordinates / SolarTime -------------------------------------------


class _SolarCoordinates:
    def __init__(self, julian_day: float) -> None:
        t = (julian_day - 2451545.0) / 36525
        l0 = _mean_solar_longitude(t)
        lp = _mean_lunar_longitude(t)
        omega = _ascending_lunar_node_longitude(t)
        lam = _rad(_apparent_solar_longitude(t, l0))
        theta0 = _mean_sidereal_time(t)
        d_psi = _nutation_in_longitude(l0, lp, omega)
        d_epsilon = _nutation_in_obliquity(l0, lp, omega)
        epsilon0 = _mean_obliquity_of_the_ecliptic(t)
        epsilon_apparent = _rad(_apparent_obliquity_of_the_ecliptic(t, epsilon0))
        self.declination = _deg(math.asin(math.sin(epsilon_apparent) * math.sin(lam)))
        self.right_ascension = _unwind(_deg(math.atan2(math.cos(epsilon_apparent) * math.sin(lam), math.cos(lam))))
        self.apparent_sidereal_time = theta0 + d_psi * 3600 * math.cos(_rad(epsilon0 + d_epsilon)) / 3600


class _SolarTime:
    def __init__(self, day: date, latitude: float, longitude: float) -> None:
        jd = _julian_day(day.year, day.month, day.day, 0)
        self.latitude = latitude
        self.longitude = longitude
        self.solar = _SolarCoordinates(jd)
        self.prev = _SolarCoordinates(jd - 1)
        self.next = _SolarCoordinates(jd + 1)
        self.approx_transit = _approximate_transit(
            longitude, self.solar.apparent_sidereal_time, self.solar.right_ascension
        )
        self.transit = self._corrected_transit()
        self.sunrise = self.hour_angle(-50.0 / 60.0, False)
        self.sunset = self.hour_angle(-50.0 / 60.0, True)

    def _corrected_transit(self) -> float:
        m0 = self.approx_transit
        theta = _unwind(self.solar.apparent_sidereal_time + 360.985647 * m0)
        a = _unwind(
            _interpolate_angles(self.solar.right_ascension, self.prev.right_ascension, self.next.right_ascension, m0)
        )
        h = _quadrant_shift(theta + self.longitude - a)
        return (m0 + h / -360) * 24

    def hour_angle(self, angle: float, after_transit: bool) -> float:
        """Return `correctedHourAngle`, in hours (NaN when the sun never reaches the angle)."""
        lat = self.latitude
        d2 = self.solar.declination
        term1 = math.sin(_rad(angle)) - math.sin(_rad(lat)) * math.sin(_rad(d2))
        term2 = math.cos(_rad(lat)) * math.cos(_rad(d2))
        h0 = _deg(_acos(term1 / term2))
        if math.isnan(h0):
            return math.nan
        m = self.approx_transit + h0 / 360 if after_transit else self.approx_transit - h0 / 360
        theta = _unwind(self.solar.apparent_sidereal_time + 360.985647 * m)
        a = _unwind(
            _interpolate_angles(self.solar.right_ascension, self.prev.right_ascension, self.next.right_ascension, m)
        )
        delta = _interpolate(d2, self.prev.declination, self.next.declination, m)
        h = theta + self.longitude - a
        altitude = _altitude_of_celestial_body(lat, delta, h)
        term3 = altitude - angle
        term4 = 360 * math.cos(_rad(delta)) * math.cos(_rad(lat)) * math.sin(_rad(h))
        return (m + term3 / term4) * 24

    def afternoon(self, shadow_length: int) -> float:
        tangent = abs(self.latitude - self.solar.declination)
        inverse = shadow_length + math.tan(_rad(tangent))
        return self.hour_angle(_deg(math.atan(1.0 / inverse)), True)

    def valid(self) -> bool:
        return not math.isnan(self.sunrise) and not math.isnan(self.sunset)


def _utc(day: date, hours: float) -> datetime | None:
    """`TimeComponents(hours).utcDate(day)`: None stands for an invalid Date."""
    if math.isnan(hours) or math.isinf(hours):
        return None
    h = math.floor(hours)
    minutes = math.floor((hours - h) * 60)
    seconds = math.floor((hours - (h + minutes / 60)) * 60 * 60)
    return datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(hours=h, minutes=minutes, seconds=seconds)


def _resolve_polar_circle(resolver: str, day: date, latitude: float, longitude: float) -> tuple[_SolarTime, _SolarTime]:
    tomorrow = day + timedelta(days=1)
    default = (_SolarTime(day, latitude, longitude), _SolarTime(tomorrow, latitude, longitude))
    if resolver == AQRAB_YAUM:
        days_added, direction = 1, 1
        while days_added <= math.ceil(365 / 2):
            test = day + timedelta(days=direction * days_added)
            solar = _SolarTime(test, latitude, longitude)
            following = _SolarTime(test + timedelta(days=1), latitude, longitude)
            if solar.valid() and following.valid():
                return solar, following
            days_added += 0 if direction > 0 else 1
            direction = -direction
        return default
    if resolver == AQRAB_BALAD:
        step = math.copysign(0.5, latitude) if latitude else 0
        lat = latitude - step
        while True:
            solar = _SolarTime(day, lat, longitude)
            following = _SolarTime(tomorrow, lat, longitude)
            if solar.valid() and following.valid():
                return solar, following
            if abs(lat) < 65:
                return default
            lat -= step
    return default


def _rounded_minute(moment: datetime, rounding: str) -> datetime:
    seconds = moment.second
    offset = 60 - seconds if seconds >= 30 else -seconds
    if rounding == UP:
        offset = 60 - seconds
    elif rounding == NONE:
        offset = 0
    return moment.replace(microsecond=0) + timedelta(seconds=offset)


def _day_of_year(day: date) -> int:
    return day.timetuple().tm_yday


def prayer_times(day: date, latitude: float, longitude: float, params: CalculationParameters) -> dict[str, datetime]:
    """Return the prayer times (UTC, rounded to the minute) of a calendar day.

    `day` is the local calendar day, as `new PrayerTimes(coordinates, date, params)`
    of adhan-js reads `date.getFullYear()/getMonth()/getDate()`.
    """
    solar = _SolarTime(day, latitude, longitude)
    tomorrow = day + timedelta(days=1)
    tomorrow_solar = _SolarTime(tomorrow, latitude, longitude)

    dhuhr = _utc(day, solar.transit)
    sunrise = _utc(day, solar.sunrise)
    sunset = _utc(day, solar.sunset)

    if (
        sunrise is None or sunset is None or math.isnan(tomorrow_solar.sunrise)
    ) and params.polar_circle_resolution != UNRESOLVED:
        solar, tomorrow_solar = _resolve_polar_circle(params.polar_circle_resolution, day, latitude, longitude)
        dhuhr = _utc(day, solar.transit)
        sunrise = _utc(day, solar.sunrise)
        sunset = _utc(day, solar.sunset)

    if sunrise is None or sunset is None or dhuhr is None:
        raise ValueError("The sun does not rise or set on this day at this place")

    asr = _utc(day, solar.afternoon(2 if params.madhab == HANAFI else 1))
    tomorrow_sunrise = _utc(tomorrow, tomorrow_solar.sunrise)
    if asr is None or tomorrow_sunrise is None:
        raise ValueError("The sun does not rise or set on this day at this place")
    night = (tomorrow_sunrise - sunset).total_seconds()
    moonsighting = params.method == "MoonsightingCommittee"
    fajr_portion, isha_portion = params.night_portions()

    fajr = _utc(day, solar.hour_angle(-params.fajr_angle, False))
    if moonsighting and latitude >= 55:
        fajr = sunrise - timedelta(seconds=night / 7)
    if moonsighting:
        safe_fajr = _season_adjusted_morning_twilight(latitude, _day_of_year(day), day.year, sunrise)
    else:
        safe_fajr = sunrise - timedelta(seconds=fajr_portion * night)
    if fajr is None or safe_fajr > fajr:
        fajr = safe_fajr

    if params.isha_interval > 0:
        isha = sunset + timedelta(minutes=params.isha_interval)
    else:
        isha = _utc(day, solar.hour_angle(-params.isha_angle, True))
        if moonsighting and latitude >= 55:
            isha = sunset + timedelta(seconds=night / 7)
        if moonsighting:
            safe_isha = _season_adjusted_evening_twilight(latitude, _day_of_year(day), day.year, sunset, params.shafaq)
        else:
            safe_isha = sunset + timedelta(seconds=isha_portion * night)
        if isha is None or safe_isha < isha:
            isha = safe_isha

    maghrib = sunset
    if params.maghrib_angle:
        angle_based = _utc(day, solar.hour_angle(-params.maghrib_angle, True))
        if angle_based is not None and sunset < angle_based < isha:
            maghrib = angle_based

    def adjusted(name: str, moment: datetime) -> datetime:
        minutes = (params.adjustments.get(name) or 0) + (params.method_adjustments.get(name) or 0)
        return _rounded_minute(moment + timedelta(minutes=minutes), params.rounding)

    return {
        "fajr": adjusted("fajr", fajr),
        "sunrise": adjusted("sunrise", sunrise),
        "dhuhr": adjusted("dhuhr", dhuhr),
        "asr": adjusted("asr", asr),
        "maghrib": adjusted("maghrib", maghrib),
        "isha": adjusted("isha", isha),
    }
