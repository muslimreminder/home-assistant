# Muslim Reminder for Home Assistant

[Français](README.fr.md)

Bring [Muslim Reminder](https://muslim-reminder.com) to your home:

- **Prayer times** in Home Assistant, computed exactly as the Muslim Reminder app computes them (same
  library, same methods, same settings, checked against the app's library on 6,912 days × places × methods);
- **salawat reminders** (prayer upon the Prophet ﷺ) played on the speakers of the house, every 5 to 60 minutes,
  with quiet hours;
- **the adhan** played at prayer time, prayer by prayer (silent, short, full);
- all of it **switched by the house**: someone at home, a baby asleep, the TV on… with switches your automations
  control, or conditions set once in the options;
- events, actions and blueprints to do anything else at prayer time (lights, TV, heating…).

No account, no cloud: the times are computed locally. Only the sounds come from the Muslim Reminder CDN.

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=muslimreminder&repository=home-assistant&category=integration)

Or in HACS → ⋮ → *Custom repositories*: `https://github.com/muslimreminder/home-assistant`, type *Integration*.
Download **Muslim Reminder**, then restart Home Assistant.

### By hand

Copy `custom_components/muslim_reminder` into the `custom_components` folder of your configuration, then restart.

### Add a place

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=muslim_reminder)

*Settings → Devices & services → Add integration → Muslim Reminder*:

- **Location**: your home by default;
- **Calculation method**: *Automatic* picks the method of the country set in Home Assistant, as the app does
  (France → France 18°, Morocco → Moroccan ministry, Saudi Arabia → Umm al-Qura…). All the methods of the app
  are there;
- **Madhab**: Hanafi, or Shafi'i/Maliki/Hanbali (standard Asr).

Several places can be added (a second home, a mosque…). *Reconfigure* moves a place.

Then open **Configure** (the options):

| Section | What |
| --- | --- |
| Speakers | The media players of the salawat reminders, those of the adhan, and *Play as an announcement* (on speakers that support it — Sonos, Music Assistant, ESPHome… — the music pauses and resumes after). |
| Conditions | Entities the reminders depend on: *only when all of these are active*, *never while one of these is active*, separately for the salawat and the adhan. |
| Calculation | Method, madhab, adjustments in minutes for each prayer, custom angles — the settings of the app. |
| Sounds | Your own sound instead of those of the app (a URL, or a `media-source://` id from the media browser). |

An entity is **active** when its state is `on`, `home`, `open`, `playing`, `active` or `detected`, or a number
above 0 — `zone.home` counts the people at home, so *only when `zone.home` is active* means "when someone is home".

## Entities

With a place named *Muslim Reminder* (the ids follow the language of Home Assistant when the place is added):

| Entity | |
| --- | --- |
| `sensor.muslim_reminder_fajr` … `_sunrise`, `_dhuhr`, `_asr`, `_maghrib`, `_isha` | Today's times (timestamps; attribute `tomorrow`). Usable as time triggers. |
| `sensor.muslim_reminder_next_prayer` | Time of the next of the five prayers (attribute `prayer`). |
| `sensor.muslim_reminder_next_prayer_name` | `fajr`, `dhuhr`, `asr`, `maghrib` or `isha`. |
| `sensor.muslim_reminder_next_salawat_reminder` | Time of the next salawat reminder (unknown when they are off). |
| `sensor.muslim_reminder_calculation_method` | The method in use (diagnostic). |
| `switch.muslim_reminder_salawat_reminders` | Salawat reminders on/off (off by default, as in the app). |
| `switch.muslim_reminder_quiet_hours` | No salawat reminder between the two times below (on by default). |
| `time.muslim_reminder_quiet_hours_start` / `_end` | 23:30 and 09:30 by default, as in the app. |
| `number.muslim_reminder_salawat_interval` | 5 to 60 minutes (25 by default). Reminders fall at 00:00 + n × interval. |
| `select.muslim_reminder_salawat_sound` | The 7 reminder sounds of the app (Choice 2 by default). |
| `switch.muslim_reminder_adhan` | All the adhans on/off. |
| `select.muslim_reminder_fajr_adhan` … `_isha_adhan` | Silent (default, as in the app), short adhan (30 s) or full adhan. |
| `select.muslim_reminder_muezzin` | The adhans of the app. |
| `number.muslim_reminder_salawat_volume` / `_adhan_volume` | Volume in %; 0 leaves the speakers as they are. Without announcement, the previous volume comes back after the sound. |
| `button.muslim_reminder_play_a_salawat_reminder` / `_play_the_adhan` / `_stop_the_speakers` | Try it now. |
| `event.muslim_reminder_prayer_time` | Fires at each of the six times (event type = the prayer). |
| `event.muslim_reminder_salawat_reminder` | Fires at each salawat reminder. |

The settings held by entities are restored after a restart. The sounds are also in the **media browser**
(*Media → Muslim Reminder*), playable on any speaker.

## Events and actions

- `muslim_reminder_prayer` — `{prayer, time, played, config_entry_id}` at each time (with `sunrise`);
- `muslim_reminder_salawat` — `{played, config_entry_id}` at each salawat reminder (`played` is false when the
  conditions or the lack of an available speaker kept it silent);
- `muslim_reminder.play_salawat` — play now (`entity_id`, `sound`, `volume` optional);
- `muslim_reminder.play_adhan` — play now (`entity_id`, `sound`, `full`, `volume` optional);
- `muslim_reminder.get_prayer_times` — returns the times of a day (`date` optional).

## Examples

Salawat reminders only when someone is home: *Configure → Conditions → Salawat reminders only when all of
these are active* = `zone.home`. Or with an automation (the blueprint below does it):

```yaml
triggers:
  - trigger: numeric_state
    entity_id: zone.home
    above: 0
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.muslim_reminder_salawat_reminders
```

Pause the TV at Maghrib:

```yaml
triggers:
  - trigger: event
    event_type: muslim_reminder_prayer
    event_data:
      prayer: maghrib
actions:
  - action: media_player.media_pause
    target:
      entity_id: media_player.tv
```

Warm the bathroom 30 minutes before Fajr:

```yaml
triggers:
  - trigger: time
    at:
      entity_id: sensor.muslim_reminder_fajr
      offset: "-00:30:00"
actions:
  - action: climate.turn_on
    target:
      entity_id: climate.bathroom
```

Times of tomorrow in a script:

```yaml
- action: muslim_reminder.get_prayer_times
  data:
    date: "{{ (now() + timedelta(days=1)).date() }}"
  response_variable: times
```

## Blueprints

| Blueprint | |
| --- | --- |
| [At prayer time](blueprints/automation/muslim_reminder/prayer_time.yaml) | Actions at the chosen prayers. [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fmuslimreminder%2Fhome-assistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmuslim_reminder%2Fprayer_time.yaml) |
| [Before (or after) a prayer](blueprints/automation/muslim_reminder/before_prayer.yaml) | Actions n minutes before or after a prayer. [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fmuslimreminder%2Fhome-assistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmuslim_reminder%2Fbefore_prayer.yaml) |
| [Salawat reminders when someone is home](blueprints/automation/muslim_reminder/salawat_presence.yaml) | Switches the reminders with the presence. [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fmuslimreminder%2Fhome-assistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmuslim_reminder%2Fsalawat_presence.yaml) |

## How the times are computed

`custom_components/muslim_reminder/adhan.py` is a line-by-line port of [adhan-js](https://github.com/batoulapps/adhan-js)
4.4.3, the library of the app, with the parameters the app builds: the method (including the app's own ones,
France 12°/15°/18°, Morocco, Algeria, Tunisia, Gulf, Russia, Kemenag…), the madhab, the minute adjustments,
the custom angles and the *TwilightAngle* rule for high latitudes. Where the sun neither rises nor sets
(beyond the polar circles), the times of the nearest latitude where it does are used.

The day is the local day of Home Assistant (its time zone).

## Sounds

The sounds are those of the app, served by `https://cdn.muslim-reminder.com/v1/sounds/` (the speakers fetch
them directly: Home Assistant does not need to be reachable from them). `scripts/upload-sounds.sh` publishes
them from the app repository.

## Development

```sh
uv venv --python 3.14 && uv pip install -r requirements_test.txt ruff
uv run pytest
uv run ruff format . && uv run ruff check .
```

`tests/fixtures/adhan_reference.json` is written by adhan-js itself:

```sh
npm install --prefix /tmp/adhan-ref adhan@4.4.3
NODE_PATH=/tmp/adhan-ref/node_modules TZ=UTC node scripts/adhan_reference.mjs
```

A release is a tag `vX.Y.Z` equal to the `version` of `manifest.json`: the *Release* workflow publishes it and
HACS offers the update.

## License

MIT. The sounds are not part of this repository.
