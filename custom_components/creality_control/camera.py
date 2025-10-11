"""Camera support for Creality K1C and other models with built-in cameras."""
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
    
    # Check if camera is available
    if coordinator.data and coordinator.data.get("video", 0) == 1:
        async_add_entities([CrealityCamera(coordinator)])

class CrealityCamera(Camera):
    """Representation of a Creality printer camera."""

    def __init__(self, coordinator):
        """Initialize the camera."""
        super().__init__()
        self.coordinator = coordinator
        self._attr_name = f"Creality {coordinator.data.get('model', 'Printer')} Camera"
        self._attr_unique_id = f"{coordinator.config['host']}_camera"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config['host'])},
            "name": f"Creality {coordinator.data.get('model', 'Printer')}",
            "manufacturer": "Creality",
            "model": coordinator.data.get('model', 'Printer'),
            "sw_version": coordinator.data.get("modelVersion", "Unknown") if coordinator.data else "Unknown",
            "suggested_area": "Workshop",
            "device_type": "3d_printer"
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

    async def async_camera_image(self, width=None, height=None):
        """Return bytes of camera image."""
        if not self.coordinator.data or self.coordinator.data.get("video", 0) != 1:
            return None
            
        try:
            import aiohttp
            camera_url = f"http://{self.coordinator.config['host']}:8080/?action=stream"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(camera_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.read()
        except Exception as e:
            _LOGGER.error(f"Failed to get camera image: {e}")
            return None
        
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
