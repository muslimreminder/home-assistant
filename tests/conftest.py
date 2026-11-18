"""Fixtures of the tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.muslim_reminder.const import (
    CONF_ADHAN_PLAYERS,
    CONF_MADHAB,
    CONF_METHOD,
    CONF_SALAWAT_PLAYERS,
    DOMAIN,
)

PARIS = {CONF_LATITUDE: 48.8566, CONF_LONGITUDE: 2.3522}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> Generator[None]:
    """Load custom_components/ in every test."""
    yield


@pytest.fixture
async def paris(hass: HomeAssistant) -> None:
    """Home Assistant in Paris, France."""
    await hass.config.async_update(
        latitude=PARIS[CONF_LATITUDE], longitude=PARIS[CONF_LONGITUDE], time_zone="Europe/Paris", country="FR"
    )


@pytest.fixture
def entry() -> MockConfigEntry:
    """A place in Paris, with a speaker for each kind of sound."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Maison",
        data=PARIS,
        options={
            CONF_METHOD: "auto",
            CONF_MADHAB: "shafi",
            CONF_SALAWAT_PLAYERS: ["media_player.salon"],
            CONF_ADHAN_PLAYERS: ["media_player.salon", "media_player.cuisine"],
        },
        unique_id="48.8566_2.3522",
    )


@pytest.fixture
def no_setup() -> Generator[None]:
    """Config flow tests do not set the entry up."""
    with patch("custom_components.muslim_reminder.async_setup_entry", return_value=True):
        yield
