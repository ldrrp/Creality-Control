from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry  
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Creality Control buttons from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    buttons = [
        CrealityControlButton(coordinator, "Pause/Resume Print", "PRINT_PAUSE"),
        CrealityControlButton(coordinator, "Stop Print", "PRINT_STOP"),
    ]
    
    # Add K1C-specific buttons if available
    if coordinator.data and coordinator.data.get("model") in ["K1C", "K1", "K1 Max"]:
        buttons.extend([
            CrealityControlButton(coordinator, "Home All Axes", "G28"),
            CrealityControlButton(coordinator, "Home X Axis", "G28 X"),
            CrealityControlButton(coordinator, "Home Y Axis", "G28 Y"),
            CrealityControlButton(coordinator, "Home Z Axis", "G28 Z"),
            CrealityControlButton(coordinator, "Emergency Stop", "M112"),
            CrealityControlButton(coordinator, "Toggle Fan", "M106 S255"),
            CrealityControlButton(coordinator, "Turn Off Fan", "M106 S0"),
        ])
    
    async_add_entities(buttons)

class CrealityControlButton(ButtonEntity):
    """Defines a Creality Control button."""

    def __init__(self, coordinator, name, command):
        super().__init__()
        self.coordinator = coordinator
        self._attr_name = name
        self._command = command
        self._attr_unique_id = f"{coordinator.config['host']}_{command}"

    async def async_press(self):
        """Handle the button press."""
        await self.coordinator.send_command(self._command)

    @property
    def device_info(self):
        """Return information about the device this button is part of."""
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

