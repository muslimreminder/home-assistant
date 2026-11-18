"""Constants of the Muslim Reminder integration.

The calculation methods, the country table and the sounds mirror the
Muslim Reminder app (src/features/salat and src/features/reminder of the
app), so that a house shows and plays the same thing as the phone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
import logging

from .adhan import CalculationParameters, calculation_method

DOMAIN = "muslim_reminder"
LOGGER = logging.getLogger(__package__)

# The five prayers, and the six times (with sunrise, "shuruq").
PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")
TIMES = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")

# Bus events, for automations and blueprints.
EVENT_PRAYER = f"{DOMAIN}_prayer"
EVENT_SALAWAT = f"{DOMAIN}_salawat"

# --- Configuration (config entry data and options) -------------------------

CONF_METHOD = "method"
CONF_MADHAB = "madhab"
CONF_ADJUSTMENTS = "adjustments"
CONF_FAJR_ANGLE = "fajr_angle"
CONF_ISHA_ANGLE = "isha_angle"
CONF_MAGHRIB_ANGLE = "maghrib_angle"
CONF_SALAWAT_PLAYERS = "salawat_players"
CONF_ADHAN_PLAYERS = "adhan_players"
CONF_SALAWAT_REQUIRED = "salawat_required"
CONF_SALAWAT_BLOCKING = "salawat_blocking"
CONF_ADHAN_REQUIRED = "adhan_required"
CONF_ADHAN_BLOCKING = "adhan_blocking"
CONF_ANNOUNCE = "announce"
CONF_SALAWAT_MEDIA = "salawat_media"
CONF_ADHAN_MEDIA = "adhan_media"
CONF_SOUND_BASE_URL = "sound_base_url"

METHOD_AUTO = "AUTO"
MADHAB_SHAFI = "shafi"
MADHAB_HANAFI = "hanafi"
MADHABS = (MADHAB_SHAFI, MADHAB_HANAFI)

DEFAULT_SOUND_BASE_URL = "https://cdn.muslim-reminder.com/v1/sounds"

# Runtime settings, held by entities (and restored after a restart), with
# the defaults of the app (ReminderStore and salat.store).
DEFAULT_SALAWAT_INTERVAL = 25
DEFAULT_QUIET_FROM = time(23, 30)
DEFAULT_QUIET_TO = time(9, 30)
DEFAULT_SALAWAT_SOUND = "reminder_2"
DEFAULT_ADHAN_SOUND = "adhan_1"

# What each prayer plays: nothing, the short adhan (30 s) or the whole adhan.
MODE_MUTE = "mute"
MODE_SHORT = "short"
MODE_FULL = "full"
ADHAN_MODES = (MODE_MUTE, MODE_SHORT, MODE_FULL)

# States that make an entity "active" for the conditions of the options.
ACTIVE_STATES = frozenset({"on", "home", "open", "true", "playing", "active", "detected"})


# --- Calculation methods ----------------------------------------------------


def _other(
    fajr: float, isha: float, interval: float = 0, maghrib_angle: float = 0, **adjustments: float
) -> CalculationParameters:
    params = CalculationParameters("Other", fajr, isha, interval, maghrib_angle)
    params.method_adjustments.update(adjustments)
    return params


# Same keys as `Methods` of the app (SalatConstants.ts), typos included, so
# that a value can be copied from one to the other.
METHODS = {
    "MUSLIM_WORLD_LEAGUE": lambda: calculation_method("MuslimWorldLeague"),
    "MOONSIGHTING_COMMITEE": lambda: calculation_method("MoonsightingCommittee"),
    "NORTH_AMERICA": lambda: calculation_method("NorthAmerica"),
    "EGYPT": lambda: calculation_method("Egyptian"),
    "UMM_ALQURA": lambda: calculation_method("UmmAlQura"),
    "KARACHI": lambda: calculation_method("Karachi"),
    "TEHRAN": lambda: calculation_method("Tehran"),
    "KUWAIT": lambda: calculation_method("Kuwait"),
    "SINGAPORE": lambda: calculation_method("Singapore"),
    "QATAR": lambda: calculation_method("Qatar"),
    "TURQEY": lambda: calculation_method("Turkey"),
    "DUBAI": lambda: calculation_method("Dubai"),
    "GULF": lambda: _other(18.2, 18.2),
    "MOROCCO": lambda: _other(18.0, 17.0),
    "GULF_2": lambda: _other(19.5, 0, 90),
    "FRANCE_UOIF": lambda: _other(12.0, 12.0),
    "FRANCE_15": lambda: _other(15.0, 15.0),
    "FRANCE_18": lambda: _other(18.0, 18.0),
    "RUSSIA": lambda: _other(16.0, 15.0),
    "JAFARI": lambda: _other(16.0, 14.0, 0, 4.0),
    "KEMENAG": lambda: _other(20.0, 18.0),
    "ALGERIA": lambda: _other(18.0, 17.0, maghrib=3),
    "BRUNEI": lambda: _other(20.0, 18.0),
    "TUNISIA": lambda: _other(18.0, 18.0),
    "CUSTOM": lambda: calculation_method("Other"),
}

# `CountryToMethod` of the app: the method of the automatic mode.
COUNTRY_TO_METHOD = {
    "SA": "UMM_ALQURA", "AE": "DUBAI", "BH": "GULF", "QA": "QATAR", "KW": "KUWAIT",
    "OM": "GULF", "YE": "GULF", "IQ": "KARACHI", "IR": "TEHRAN", "TR": "TURQEY",
    "MA": "MOROCCO", "DZ": "ALGERIA", "TN": "TUNISIA", "EG": "EGYPT", "SD": "UMM_ALQURA",
    "DJ": "UMM_ALQURA", "PK": "KARACHI", "IN": "KARACHI", "BD": "KARACHI", "AF": "KARACHI",
    "ID": "KEMENAG", "SG": "SINGAPORE", "BN": "BRUNEI", "KZ": "RUSSIA", "KG": "RUSSIA",
    "UZ": "RUSSIA", "TM": "RUSSIA", "TJ": "RUSSIA", "RU": "RUSSIA", "FR": "FRANCE_18",
    "BE": "FRANCE_18", "US": "NORTH_AMERICA", "CA": "NORTH_AMERICA",
}  # fmt: skip

FALLBACK_METHOD = "MUSLIM_WORLD_LEAGUE"


# --- Sounds -----------------------------------------------------------------


@dataclass(frozen=True)
class Sound:
    """A sound of the app, served by the Muslim Reminder CDN."""

    key: str
    file: str
    duration: float
    full_file: str | None = None
    full_duration: float | None = None


# reminder_1…7 of the app (reminder/data/Reminders.ts), "Choice 1…7".
SALAWAT_SOUNDS = {
    sound.key: sound
    for sound in (
        Sound("reminder_1", "salawat/reminder_1.mp3", 1.6),
        Sound("reminder_2", "salawat/reminder_2.mp3", 15.1),
        Sound("reminder_3", "salawat/reminder_3.mp3", 2.0),
        Sound("reminder_4", "salawat/reminder_4.mp3", 2.5),
        Sound("reminder_5", "salawat/reminder_5.mp3", 4.4),
        Sound("reminder_6", "salawat/reminder_6.mp3", 14.0),
        Sound("reminder_7", "salawat/reminder_7.mp3", 6.0),
    )
}

# The adhans of the app (salat/data/Adhans.android.ts), short and full
# versions. Karl Jenkins' "The Armed Man" (a commercial recording) and the
# iOS-only Dubai One version are not served.
ADHAN_SOUNDS = {
    sound.key: sound
    for sound in (
        Sound("adhan_1", "adhan/adhan_1.mp3", 30.0, "adhan/adhan_1_full.mp3", 213.7),
        Sound("adhan_2", "adhan/adhan_2.mp3", 30.0, "adhan/adhan_2_full.mp3", 237.8),
        Sound("adhan_5", "adhan/adhan_5.mp3", 30.0, "adhan/adhan_5_full.mp3", 322.8),
        Sound("adhan_6", "adhan/adhan_6.mp3", 30.0, "adhan/adhan_6_full.mp3", 195.8),
        Sound("adhan_7", "adhan/adhan_7.mp3", 30.0, "adhan/adhan_7_full.mp3", 242.6),
        Sound("adhan_8", "adhan/adhan_8.mp3", 30.0, "adhan/adhan_8_full.mp3", 203.4),
        Sound("adhan_9", "adhan/adhan_9.mp3", 30.0, "adhan/adhan_9_full.mp3", 257.1),
        Sound("adhan_10", "adhan/adhan_10.mp3", 193.6),
        Sound("adhan_11", "adhan/adhan_11.mp3", 131.6),
    )
}
