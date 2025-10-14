import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Creality Control number entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    numbers = [
        CrealityTempNumber(coordinator, "nozzle", "Nozzle Temperature", 0, 300, 1, "°C"),
        CrealityTempNumber(coordinator, "bed", "Bed Temperature", 0, 150, 1, "°C"),
    ]
    async_add_entities(numbers)

class CrealityTempNumber(CoordinatorEntity, NumberEntity):
    """Defines a Creality Temperature Control number entity."""

    def __init__(self, coordinator, temp_type, name_suffix, min_value, max_value, step, unit_of_measurement):
        super().__init__(coordinator)
        self._temp_type = temp_type
        self._attr_name = f"Creality {name_suffix}"
        self._attr_unique_id = f"{coordinator.config['host']}_temp_{temp_type}"
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_mode = NumberMode.BOX

    @property
    def name(self):
        """Return the name of the number entity."""
        return self._attr_name

    @property
    def unique_id(self):
        """Return a unique identifier for this number entity."""
        return self._attr_unique_id

    @property
    def native_value(self):
        """Return the current target temperature."""
        if not self.coordinator.data:
            return 0
        
        if self._temp_type == "nozzle":
            return float(self.coordinator.data.get("targetNozzleTemp", 0))
        elif self._temp_type == "bed":
            return float(self.coordinator.data.get("targetBedTemp0", 0))
        
        return 0

    async def async_set_native_value(self, value: float):
        """Set the target temperature."""
        temperature = int(value)
        success = await self.coordinator.send_temp_command(self._temp_type, temperature)
        if not success:
            _LOGGER.warning(f"Failed to set {self._temp_type} temperature to {temperature}°C - WebSocket may be disconnected")

    @property
    def available(self):
        """Return True if the number entity is available."""
        # Check if WebSocket is healthy
        if hasattr(self.coordinator, 'ws_client') and self.coordinator.ws_client:
            return self.coordinator.ws_client.is_healthy() and self.coordinator.last_update_success
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return information about the device this number entity is part of."""
        # Try to detect printer model from data if available
        model = "Creality Printer"
        if self.coordinator.data:
            if "model" in self.coordinator.data:
                model = self.coordinator.data["model"]
            elif "printerModel" in self.coordinator.data:
                model = self.coordinator.data["printerModel"]
            elif "detected_model" in self.coordinator.data:
                model = self.coordinator.data["detected_model"]
        
        return {
            "identifiers": {(DOMAIN, self.coordinator.config['host'])},
            "name": f"Creality {model}",
            "manufacturer": "Creality",
            "model": model,
            "sw_version": self._parse_firmware_version(),
            "suggested_area": "Workshop",
            "configuration_url": f"http://{self.coordinator.config['host']}:80"
        }

    def _parse_firmware_version(self):
        """Parse firmware version from modelVersion data."""
        if not self.coordinator.data:
            return "Unknown"
            
        raw_version = self.coordinator.data.get("modelVersion", "")
        if not raw_version:
            return "Unknown"
        
        # Parse the version string: "printer hw ver:;printer sw ver:;DWIN hw ver:CR4CU220812S11;DWIN sw ver:1.3.3.46;"
        try:
            # Split by semicolon and find the DWIN software version
            parts = raw_version.split(';')
            for part in parts:
                if 'DWIN sw ver:' in part:
                    version = part.replace('DWIN sw ver:', '').strip()
                    if version:
                        return version
            
            # If no DWIN version found, try to find any version
            for part in parts:
                if 'sw ver:' in part and part.replace('sw ver:', '').strip():
                    version = part.replace('sw ver:', '').strip()
                    if version:
                        return version
                        
        except Exception:
            pass
        
        # Fallback to raw version if parsing fails
        return raw_version
