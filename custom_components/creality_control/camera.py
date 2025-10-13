"""Camera support for Creality K1C and other models with built-in cameras."""
import asyncio
import logging
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Creality camera from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Always add the camera entity - it will handle availability internally
    async_add_entities([CrealityCamera(coordinator)])

class CrealityCamera(Camera):
    """Representation of a Creality printer camera."""

    def __init__(self, coordinator):
        """Initialize the camera."""
        super().__init__()
        self.coordinator = coordinator
        self._attr_name = f"Creality {coordinator.data.get('model', 'Printer') if coordinator.data else 'Printer'} Camera"
        self._attr_unique_id = f"{coordinator.config['host']}_camera"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config['host'])},
            "name": f"Creality {coordinator.data.get('model', 'Printer') if coordinator.data else 'Printer'}",
            "manufacturer": "Creality",
            "model": coordinator.data.get('model', 'Printer') if coordinator.data else 'Printer',
            "sw_version": coordinator.data.get("modelVersion", "Unknown") if coordinator.data else "Unknown",
            "suggested_area": "Workshop"
        }

    @property
    def name(self):
        """Return the name of the camera."""
        return self._attr_name

    @property
    def unique_id(self):
        """Return a unique identifier for this camera."""
        return self._attr_unique_id

    @property
    def device_info(self):
        """Return information about the device this camera is part of."""
        return self._attr_device_info

    @property
    def available(self):
        """Return True if the camera is available."""
        return (self.coordinator.data and 
                self.coordinator.data.get("video", 0) == 1 and
                self.coordinator.last_update_success)

    async def async_camera_image(self, width=None, height=None):
        """Return bytes of camera image."""
        if not self.coordinator.data or self.coordinator.data.get("video", 0) != 1:
            _LOGGER.debug("Camera not available - video disabled or no data")
            return None
            
        try:
            import aiohttp
            # Use the known working camera URL
            camera_url = f"http://{self.coordinator.config['host']}:8080/?action=stream"
            _LOGGER.debug(f"Attempting to fetch camera image from: {camera_url}")
            
            # Headers that might be needed for MJPEG streams
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Home Assistant)',
                'Accept': 'image/jpeg, image/png, image/*',
                'Connection': 'keep-alive',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(camera_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    _LOGGER.debug(f"Camera response status: {response.status}")
                    _LOGGER.debug(f"Camera response content-type: {response.headers.get('content-type', 'unknown')}")
                    if response.status == 200:
                        image_data = await response.read()
                        _LOGGER.debug(f"Successfully fetched camera image ({len(image_data)} bytes)")
                        return image_data
                    else:
                        _LOGGER.warning(f"Camera URL {camera_url} returned status {response.status}")
                        return None
            
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Camera connection error: {e}")
            return None
        except asyncio.TimeoutError:
            _LOGGER.error("Camera request timeout")
            return None
        except Exception as e:
            _LOGGER.error(f"Failed to get camera image: {e}")
            return None

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self.coordinator.data.get("videoElapse", 0) == 1 if self.coordinator.data else False

    @property
    def brand(self):
        """Return the camera brand."""
        return "Creality"

    @property
    def model(self):
        """Return the camera model."""
        return f"{self.coordinator.data.get('model', 'Printer')} Camera" if self.coordinator.data else "Printer Camera"
