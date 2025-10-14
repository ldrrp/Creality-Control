import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Creality Control switch entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    switches = [
        CrealitySwitch(coordinator, "fan", "Fan", "fan_on", "fan_off"),
        CrealitySwitch(coordinator, "light", "Light", "light_on", "light_off"),
    ]
    async_add_entities(switches)

class CrealitySwitch(CoordinatorEntity, SwitchEntity):
    """Defines a Creality Control switch entity."""

    def __init__(self, coordinator, switch_type, name_suffix, on_command, off_command):
        super().__init__(coordinator)
        self._switch_type = switch_type
        self._attr_name = f"Creality {name_suffix}"
        self._attr_unique_id = f"{coordinator.config['host']}_switch_{switch_type}"
        self._on_command = on_command
        self._off_command = off_command
        self._use_websocket = switch_type in ["light", "fan"]  # Use WebSocket for both light and fan

    @property
    def name(self):
        """Return the name of the switch."""
        return self._attr_name

    @property
    def unique_id(self):
        """Return a unique identifier for this switch."""
        return self._attr_unique_id

    @property
    def is_on(self):
        """Return the current state of the switch."""
        if not self.coordinator.data:
            return False
        
        if self._switch_type == "fan":
            return bool(self.coordinator.data.get("fan", 0))
        elif self._switch_type == "light":
            return bool(self.coordinator.data.get("lightSw", 0))
        
        return False

    async def async_turn_on(self):
        """Turn the switch on."""
        if self._use_websocket:
            # Use WebSocket JSON for control
            if self._switch_type == "light":
                success = await self.coordinator.send_websocket_command({"method": "set", "params": {"lightSw": 1}})
            elif self._switch_type == "fan":
                success = await self.coordinator.send_websocket_command({"method": "set", "params": {"fan": 1}})
            else:
                success = await self.coordinator.send_command(self._on_command)
        else:
            # Use G-code for other controls
            success = await self.coordinator.send_command(self._on_command)
        
        if not success:
            _LOGGER.warning(f"Failed to turn on {self._switch_type} - WebSocket may be disconnected")

    async def async_turn_off(self):
        """Turn the switch off."""
        if self._use_websocket:
            # Use WebSocket JSON for control
            if self._switch_type == "light":
                success = await self.coordinator.send_websocket_command({"method": "set", "params": {"lightSw": 0}})
            elif self._switch_type == "fan":
                success = await self.coordinator.send_websocket_command({"method": "set", "params": {"fan": 0}})
            else:
                success = await self.coordinator.send_command(self._off_command)
        else:
            # Use G-code for other controls
            success = await self.coordinator.send_command(self._off_command)
        
        if not success:
            _LOGGER.warning(f"Failed to turn off {self._switch_type} - WebSocket may be disconnected")

    @property
    def available(self):
        """Return True if the switch is available."""
        # Check if WebSocket is healthy
        if hasattr(self.coordinator, 'ws_client') and self.coordinator.ws_client:
            return self.coordinator.ws_client.is_healthy() and self.coordinator.last_update_success
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return information about the device this switch is part of."""
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
