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
        # Get product image based on model
        model = coordinator.data.get('model', 'Printer') if coordinator.data else 'Printer'
        product_image = self._get_product_image(model)
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config['host'])},
            "name": f"Creality {model}",
            "manufacturer": "Creality",
            "model": model,
            "sw_version": self._parse_firmware_version(),
            "suggested_area": "Workshop",
            "configuration_url": f"http://{coordinator.config['host']}:80",
            "product_image": product_image
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
                async with session.get(camera_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    _LOGGER.debug(f"Camera response status: {response.status}")
                    _LOGGER.debug(f"Camera response content-type: {response.headers.get('content-type', 'unknown')}")
                    if response.status == 200:
                        # For MJPEG streams, we need to extract a single JPEG frame
                        try:
                            async with asyncio.timeout(15):
                                # Read the stream data in chunks until we have enough
                                stream_data = b""
                                async for chunk in response.content.iter_chunked(8192):
                                    stream_data += chunk
                                    # Try to extract JPEG frame after each chunk
                                    jpeg_data = self._extract_jpeg_from_mjpeg(stream_data)
                                    if jpeg_data:
                                        _LOGGER.debug(f"Successfully extracted JPEG frame ({len(jpeg_data)} bytes)")
                                        return jpeg_data
                                    # Stop if we've read too much data (safety limit)
                                    if len(stream_data) > 1024*1024:  # 1MB limit
                                        _LOGGER.warning("Stream data too large, stopping")
                                        break
                                
                                _LOGGER.warning("Could not extract JPEG frame from MJPEG stream")
                                return None
                        except asyncio.TimeoutError:
                            _LOGGER.warning("Timeout reading camera stream data")
                            return None
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

    def _extract_jpeg_from_mjpeg(self, stream_data):
        """Extract a single JPEG frame from MJPEG stream data."""
        try:
            # MJPEG format: --boundary\r\nContent-Type: image/jpeg\r\nContent-Length: XXXX\r\n\r\n[JPEG_DATA]
            boundary_marker = b'--boundarydonotcross'
            content_length = b'Content-Length: '
            
            # Find the boundary marker
            boundary_pos = stream_data.find(boundary_marker)
            if boundary_pos == -1:
                _LOGGER.warning("No boundary marker found in stream")
                return None
            
            # Find Content-Length header
            length_start = stream_data.find(content_length, boundary_pos)
            if length_start == -1:
                _LOGGER.warning("No Content-Length header found")
                return None
            
            # Extract the content length
            length_end = stream_data.find(b'\r\n', length_start)
            if length_end == -1:
                _LOGGER.warning("Malformed Content-Length header")
                return None
            
            try:
                length_str = stream_data[length_start + len(content_length):length_end]
                jpeg_length = int(length_str)
                _LOGGER.debug(f"JPEG content length: {jpeg_length} bytes")
            except ValueError:
                _LOGGER.warning(f"Could not parse content length: {length_str}")
                return None
            
            # Find the start of JPEG data (after \r\n\r\n)
            jpeg_start_marker = b'\r\n\r\n'
            jpeg_start_pos = stream_data.find(jpeg_start_marker, boundary_pos)
            if jpeg_start_pos == -1:
                _LOGGER.warning("Could not find JPEG data start marker")
                return None
            
            jpeg_data_start = jpeg_start_pos + len(jpeg_start_marker)
            jpeg_data_end = jpeg_data_start + jpeg_length
            
            # Check if we have enough data
            if jpeg_data_end > len(stream_data):
                _LOGGER.warning(f"Not enough data: have {len(stream_data)}, need {jpeg_data_end}")
                return None
            
            # Extract the JPEG frame
            jpeg_frame = stream_data[jpeg_data_start:jpeg_data_end]
            
            # Verify it's a valid JPEG by checking the start marker
            if jpeg_frame.startswith(b'\xff\xd8'):
                _LOGGER.debug(f"Extracted JPEG frame: {len(jpeg_frame)} bytes")
                return jpeg_frame
            else:
                _LOGGER.warning("Extracted frame does not start with JPEG marker")
                return None
                
        except Exception as e:
            _LOGGER.error(f"Error extracting JPEG from MJPEG stream: {e}")
            return None

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
