"""Media source: the sounds of the app in the media browser of Home Assistant.

Media → Muslim Reminder → Salawat / Adhan: any speaker can play them, and
an automation can use their media-source:// ids.
"""

from __future__ import annotations

from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import ADHAN_SOUNDS, DEFAULT_SOUND_BASE_URL, DOMAIN, SALAWAT_SOUNDS, Sound

# Names of the app (salat:settings.adhans, reminder:reminder_choice_N).
ADHAN_NAMES = {
    "adhan_1": "Ahmad Al-Nufais",
    "adhan_2": "Hafız Mustafa Özcan",
    "adhan_5": "Traditional Adhan 1",
    "adhan_6": "Traditional Adhan 2",
    "adhan_7": "Mishary Alafasy · Version 2",
    "adhan_8": "Traditional Adhan 3",
    "adhan_9": "Mishary Alafasy · Version 3",
    "adhan_10": "Mansour Al-Zahrani",
    "adhan_11": "Traditional Adhan 4",
}
TITLES = {
    "en": {"salawat": "Salawat", "adhan": "Adhan", "choice": "Choice {n}", "short": "short"},
    "fr": {"salawat": "Salawat", "adhan": "Adhan", "choice": "Choix {n}", "short": "court"},
    "ar": {"salawat": "الصلاة على النبي ﷺ", "adhan": "الأذان", "choice": "الاختيار {n}", "short": "قصير"},
}


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    return MuslimReminderMediaSource(hass)


class MuslimReminderMediaSource(MediaSource):
    """Identifiers: salawat/<key>, adhan/<key> (full) and adhan/<key>/short."""

    name = "Muslim Reminder"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    def _base_url(self) -> str:
        for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
            if url := entry.options.get("sound_base_url"):
                return str(url).rstrip("/")
        return DEFAULT_SOUND_BASE_URL

    def _titles(self) -> dict[str, str]:
        return TITLES.get((self.hass.config.language or "en").split("-")[0], TITLES["en"])

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        parts = (item.identifier or "").split("/")
        sound: Sound | None = None
        file: str | None = None
        if len(parts) == 2 and parts[0] == "salawat" and (sound := SALAWAT_SOUNDS.get(parts[1])):
            file = sound.file
        elif len(parts) in (2, 3) and parts[0] == "adhan" and (sound := ADHAN_SOUNDS.get(parts[1])):
            file = sound.file if len(parts) == 3 or not sound.full_file else sound.full_file
        if file is None:
            raise Unresolvable(f"Unknown sound: {item.identifier}")
        return PlayMedia(f"{self._base_url()}/{file}", "audio/mpeg")

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        titles = self._titles()
        identifier = item.identifier or ""
        if identifier == "":
            return self._folder(
                "", self.name, [self._folder("salawat", titles["salawat"]), self._folder("adhan", titles["adhan"])]
            )
        if identifier == "salawat":
            children = [
                self._sound(f"salawat/{key}", titles["choice"].format(n=index + 1))
                for index, key in enumerate(SALAWAT_SOUNDS)
            ]
            return self._folder("salawat", titles["salawat"], children)
        if identifier == "adhan":
            children = []
            for key, sound in ADHAN_SOUNDS.items():
                children.append(self._sound(f"adhan/{key}", ADHAN_NAMES[key]))
                if sound.full_file:
                    children.append(self._sound(f"adhan/{key}/short", f"{ADHAN_NAMES[key]} ({titles['short']})"))
            return self._folder("adhan", titles["adhan"], children)
        raise BrowseError(f"Unknown folder: {identifier}")

    def _folder(
        self, identifier: str, title: str, children: list[BrowseMediaSource] | None = None
    ) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title=title,
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=MediaClass.MUSIC,
        )

    def _sound(self, identifier: str, title: str) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.MUSIC,
            media_content_type="audio/mpeg",
            title=title,
            can_play=True,
            can_expand=False,
        )
