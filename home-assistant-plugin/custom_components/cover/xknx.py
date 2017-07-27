import asyncio
import xknx
import voluptuous as vol

from custom_components.xknx import DATA_XKNX
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.components.cover import PLATFORM_SCHEMA, CoverDevice
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_MOVE_LONG_ADDRESS = 'move_long_address'
CONF_MOVE_SHORT_ADDRESS = 'move_short_address'
CONF_POSITION_ADDRESS = 'position_address'
CONF_POSITION_STATE_ADDRESS = 'position_state_address'
CONF_TRAVELLING_TIME_DOWN = 'travelling_time_down'
CONF_TRAVELLING_TIME_UP = 'travelling_time_up'

DEFAULT_TRAVEL_TIME = 25
DEFAULT_NAME = 'XKNX Binary Sensor'
DEPENDENCIES = ['xknx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MOVE_LONG_ADDRESS): cv.string,
    vol.Optional(CONF_MOVE_SHORT_ADDRESS): cv.string,
    vol.Optional(CONF_POSITION_ADDRESS): cv.string,
    vol.Optional(CONF_POSITION_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME):
        cv.positive_int,
    vol.Optional(CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME):
        cv.positive_int,
})

@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, \
        discovery_info=None):
    """Setup the XKNX cover platform."""
    if DATA_XKNX not in hass.data \
            or not hass.data[DATA_XKNX].initialized:
        return False

    if discovery_info is not None:
        yield from add_devices_from_component(hass, add_devices)
    else:
        yield from add_devices_from_platform(hass, config, add_devices)

    return True

@asyncio.coroutine
def add_devices_from_component(hass, add_devices):
    entities = []
    for device in hass.data[DATA_XKNX].xknx.devices:
        if isinstance(device, xknx.Cover) and \
                not hasattr(device, "already_added_to_hass"):
            entities.append(XKNXCover(hass, device))
    add_devices(entities)

@asyncio.coroutine
def add_devices_from_platform(hass, config, add_devices):
    from xknx import Cover
    cover = Cover(hass.data[DATA_XKNX].xknx,
                  name= \
                      config.get(CONF_NAME),
                  group_address_long= \
                      config.get(CONF_MOVE_LONG_ADDRESS),
                  group_address_short= \
                      config.get(CONF_MOVE_SHORT_ADDRESS),
                  group_address_position_feedback= \
                      config.get(CONF_POSITION_STATE_ADDRESS),
                  group_address_position= \
                      config.get(CONF_POSITION_ADDRESS),
                  travel_time_down= \
                      config.get(CONF_TRAVELLING_TIME_DOWN),
                  travel_time_up= \
                      config.get(CONF_TRAVELLING_TIME_UP))

    cover.already_added_to_hass = True
    hass.data[DATA_XKNX].xknx.devices.add(cover)
    add_devices([XKNXCover(hass, cover)])


class XKNXCover(CoverDevice):
    """Representation of XKNX shutters"""

    def __init__(self, hass, device):
        """Initialize the cover."""
        self.device = device
        self.hass = hass
        self.register_callbacks()

        self._unsubscribe_auto_updater = None

    def register_callbacks(self):
        def after_update_callback(device):
            #pylint: disable=unused-argument
            self.update_ha()
        self.device.register_device_updated_cb(after_update_callback)


    def update_ha(self):
        self.hass.async_add_job(self.async_update_ha_state())

    @property
    def name(self):
        """Return the name of the cover."""
        return self.device.name

    @property
    def should_poll(self):
        """No polling needed for a demo cover."""
        return False

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return int(self.from_knx(self.device.current_position()))

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.device.is_closed()

    def close_cover(self, **kwargs):
        """Close the cover."""
        if not self.device.is_closed():
            self.device.set_down()
            self.start_auto_updater()

    def open_cover(self, **kwargs):
        """Open the cover."""
        if not self.device.is_open():
            self.device.set_up()
            self.start_auto_updater()

    def set_cover_position(self, position, **kwargs):
        """Move the cover to a specific position."""
        knx_position = self.to_knx(position)
        self.device.set_position(knx_position)
        self.start_auto_updater()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.device.stop()
        self.stop_auto_updater()

    #
    # UPDATER
    #

    def stop_auto_updater(self):
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    def start_auto_updater(self):
        if self._unsubscribe_auto_updater is None:
            self._unsubscribe_auto_updater = track_utc_time_change(
                self.hass, self.auto_updater_hook)

    def auto_updater_hook(self, now):
        # pylint: disable=unused-argument
        self.update_ha()
        print(self.device.current_position())
        if self.device.position_reached():
            self.stop_auto_updater()

        self.device.auto_stop_if_necessary()

    #
    # HELPER FUNCTIONS
    #

    # KNX and HASS have different understanding of open and closed:
    #
    #            KNX     HASS
    #    UP      0       100
    #    DOWN    255     0


    #TODO: use DPTScaling
    @staticmethod
    def from_knx(raw):
        return 100-round((raw/256)*100)

    @staticmethod
    def to_knx(value):
        return 255-round(value/100*255.4)

    #
    # UNUSED FUNCTIONS
    #
    def stop_cover_tilt(self, **kwargs):
        """Stop the cover tilt."""
        print("stop_cover_tilt - not implemented")

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        print("close_cover_tilt - not implemented")

    def set_cover_tilt_position(self, tilt_position, **kwargs):
        #pylint: disable=unused-argument
        """Move the cover til to a specific position."""
        print("close_cover_tilt_position - not implemented")

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        print("open_cover_tilt - not implemented")

    @property
    def current_cover_tilt_position(self):
        """Return the current tilt position of the cover."""
        return None
