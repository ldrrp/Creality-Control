from homeassistant.helpers.update_coordinator import CoordinatorEntity
from datetime import timedelta
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Creality Control sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = [
        # Print Status and Progress
        CrealitySensor(coordinator, "state", "Print State"),
        CrealitySensor(coordinator, "deviceState", "Device State"),
        CrealitySensor(coordinator, "printProgress", "Print Progress", unit_of_measurement="%"),
        CrealitySensor(coordinator, "layer", "Current Layer"),
        CrealitySensor(coordinator, "TotalLayer", "Total Layers"),
        CrealityTimeLeftSensor(coordinator, "printLeftTime", "Time Left"),
        CrealitySensor(coordinator, "printJobTime", "Print Job Time", unit_of_measurement="s"),
        CrealitySensor(coordinator, "printFileName", "Print Filename"),
        CrealitySensor(coordinator, "printId", "Print ID"),
        
        # Temperature Sensors
        CrealitySensor(coordinator, "nozzleTemp", "Nozzle Temperature", unit_of_measurement="°C"),
        CrealitySensor(coordinator, "targetNozzleTemp", "Target Nozzle Temperature", unit_of_measurement="°C"),
        CrealitySensor(coordinator, "bedTemp0", "Bed Temperature", unit_of_measurement="°C"),
        CrealitySensor(coordinator, "targetBedTemp0", "Target Bed Temperature", unit_of_measurement="°C"),
        CrealitySensor(coordinator, "boxTemp", "Box Temperature", unit_of_measurement="°C"),
        
        # Position and Movement
        CrealitySensor(coordinator, "curPosition", "Current Position"),
        CrealitySensor(coordinator, "realTimeSpeed", "Real Time Speed", unit_of_measurement="mm/s"),
        CrealitySensor(coordinator, "realTimeFlow", "Real Time Flow", unit_of_measurement="mm³/s"),
        CrealitySensor(coordinator, "curFeedratePct", "Feedrate", unit_of_measurement="%"),
        CrealitySensor(coordinator, "curFlowratePct", "Flowrate", unit_of_measurement="%"),
        
        # Fan Controls
        CrealitySensor(coordinator, "fan", "Fan Status"),
        CrealitySensor(coordinator, "fanAuxiliary", "Auxiliary Fan"),
        CrealitySensor(coordinator, "fanCase", "Case Fan"),
        CrealitySensor(coordinator, "auxiliaryFanPct", "Auxiliary Fan Speed", unit_of_measurement="%"),
        CrealitySensor(coordinator, "caseFanPct", "Case Fan Speed", unit_of_measurement="%"),
        CrealitySensor(coordinator, "modelFanPct", "Model Fan Speed", unit_of_measurement="%"),
        
        # Material and Usage
        CrealitySensor(coordinator, "usedMaterialLength", "Used Material Length", unit_of_measurement="mm"),
        CrealitySensor(coordinator, "materialDetect", "Material Detection"),
        CrealitySensor(coordinator, "materialStatus", "Material Status"),
        
        # System Information
        CrealitySensor(coordinator, "model", "Printer Model"),
        CrealitySensor(coordinator, "hostname", "Hostname"),
        CrealityFirmwareSensor(coordinator, "modelVersion", "Firmware Version"),
        CrealitySensor(coordinator, "connect", "Connection Status"),
        CrealitySensor(coordinator, "tfCard", "TF Card Status"),
        CrealitySensor(coordinator, "video", "Camera Status"),
        
        # Advanced Settings
        CrealitySensor(coordinator, "pressureAdvance", "Pressure Advance"),
        CrealitySensor(coordinator, "smoothTime", "Smooth Time", unit_of_measurement="s"),
        CrealitySensor(coordinator, "velocityLimits", "Velocity Limits", unit_of_measurement="mm/s"),
        CrealitySensor(coordinator, "accelerationLimits", "Acceleration Limits", unit_of_measurement="mm/s²"),
        CrealitySensor(coordinator, "cornerVelocityLimits", "Corner Velocity Limits", unit_of_measurement="mm/s"),
        
        # Legacy Halot sensors (for backward compatibility)
        CrealitySensor(coordinator, "printStatus", "Legacy Status"),
        CrealitySensor(coordinator, "filename", "Legacy Filename"),
        CrealityTimeLeftSensor(coordinator, "printRemainTime", "Legacy Time Left"),
        CrealitySensor(coordinator, "progress", "Legacy Progress", unit_of_measurement="%"),
        CrealitySensor(coordinator, "curSliceLayer", "Legacy Current Layer"),
        CrealitySensor(coordinator, "sliceLayerCount", "Legacy Total Layers"),
    ]
    async_add_entities(sensors)

class CrealitySensor(CoordinatorEntity):
    """Defines a single Creality sensor."""

    def __init__(self, coordinator, data_key, name_suffix, unit_of_measurement=None):
        super().__init__(coordinator)
        self.data_key = data_key
        self._attr_name = f"Creality {name_suffix}"
        self._attr_unique_id = f"{coordinator.config['host']}_{data_key}"
        self._unit_of_measurement = unit_of_measurement

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return self._attr_unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return "Unknown"
            
        # Special handling for progress calculations
        if self.data_key == "progress":
            # Try K1C format first
            if "printProgress" in self.coordinator.data:
                return self.coordinator.data["printProgress"]
            # Fallback to legacy calculation
            cur_layer = self.coordinator.data.get("curSliceLayer", 0)
            total_layers = self.coordinator.data.get("sliceLayerCount", 0)
            try:
                progress = (float(cur_layer) / float(total_layers)) * 100 if total_layers else 0
                return round(progress, 2)
            except ValueError:
                return 0
        elif self.data_key == "printProgress":
            # Direct K1C progress value
            return self.coordinator.data.get("printProgress", 0)
        elif self.data_key == "legacy_progress":
            # Legacy progress calculation
            cur_layer = self.coordinator.data.get("curSliceLayer", 0)
            total_layers = self.coordinator.data.get("sliceLayerCount", 0)
            try:
                progress = (float(cur_layer) / float(total_layers)) * 100 if total_layers else 0
                return round(progress, 2)
            except ValueError:
                return 0
        
        return self.coordinator.data.get(self.data_key, "Unknown")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement if defined."""
        return self._unit_of_measurement

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

    @property
    def device_info(self):
        """Return information about the device this sensor is part of."""
        # Try to detect printer model from data if available
        model = "Creality Printer"
        if self.coordinator.data:
            if "model" in self.coordinator.data:
                model = self.coordinator.data["model"]
            elif "printerModel" in self.coordinator.data:
                model = self.coordinator.data["printerModel"]
            elif "detected_model" in self.coordinator.data:
                model = self.coordinator.data["detected_model"]
        
        # Get product image based on model
        product_image = self._get_product_image(model)
        
        return {
            "identifiers": {(DOMAIN, self.coordinator.config['host'])},
            "name": f"Creality {model}",
            "manufacturer": "Creality",
            "model": model,
            "sw_version": self._parse_firmware_version(),
            "suggested_area": "Workshop",
            "configuration_url": f"http://{self.coordinator.config['host']}:80",
            "product_image": product_image
        }

class CrealityTimeLeftSensor(CrealitySensor):
    """Specialized sensor class for handling 'Time Left' data."""

    @property
    def state(self):
        """Return the state of the sensor, converting time to HH:MM:SS format."""
        if not self.coordinator.data:
            return "00:00:00"
        time_left = int(self.coordinator.data.get(self.data_key, 0))
        return str(timedelta(seconds=time_left))


class CrealityFirmwareSensor(CrealitySensor):
    """Specialized sensor class for handling firmware version data."""

    @property
    def state(self):
        """Return a clean firmware version."""
        if not self.coordinator.data:
            return "Unknown"
            
        raw_version = self.coordinator.data.get(self.data_key, "")
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
    def _get_product_image(self, model):
        """Get product image path based on printer model."""
        if not model:
            return None
        
        # Clean model name for filename
        model_clean = model.replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").upper()
        
        # Map common model names to image filenames
        model_mapping = {
            "K1SE": "K1_SE",
            "K1": "K1",
            "K1_MAX": "K1_MAX", 
            "K1C": "K1C",
            "ENDER_3_V3_SE": "ENDER_3_V3_SE",
            "ENDER_3_V3_KE": "ENDER_3_V3_KE",
            "ENDER_3_V3": "ENDER_3_V3",
            "ENDER_3_S1_PRO": "ENDER_3_S1_PRO",
            "ENDER_3_S1": "ENDER_3_S1",
            "ENDER_3_MAX_NEO": "ENDER_3_MAX_NEO",
            "ENDER_5_S1": "ENDER_5_S1",
            "ENDER_5_PRO": "ENDER_5_PRO",
            "ENDER_7": "ENDER_7",
            "ENDER_3_V2": "ENDER_3_V2",
            "ENDER_3_PRO": "ENDER_3_PRO",
            "ENDER_3": "ENDER_3",
            "ENDER_5": "ENDER_5",
            "CR_10": "CR_10",
            "CR_10S": "CR_10S",
            "CR_10S_PRO": "CR_10S_PRO",
            "HALOT_ONE": "HALOT_ONE",
            "HALOT_ONE_PLUS": "HALOT_ONE_PLUS",
            "HALOT_SKY": "HALOT_SKY",
            "HALOT_SKY_PRO": "HALOT_SKY_PRO",
            "HALOT_MAGE": "HALOT_MAGE",
            "HALOT_MAGE_PRO": "HALOT_MAGE_PRO",
            "HALOT_MAGE_S": "HALOT_MAGE_S",
            "HALOT_MAGE_8K": "HALOT_MAGE_8K",
            "HALOT_MAGE_8K_PRO": "HALOT_MAGE_8K_PRO",
            "HALOT_MAGE_8K_S": "HALOT_MAGE_8K_S"
        }
        
        # Get the mapped filename or use the cleaned model name
        image_filename = model_mapping.get(model_clean, model_clean)
        
        # Return the path to the product image
        return f"custom_components/creality_control/images/{image_filename}.webp"
