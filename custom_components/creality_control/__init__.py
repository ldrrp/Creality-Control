import aiohttp
import asyncio
import json
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import config_validation as cv
from homeassistant import config_entries
from datetime import timedelta
import logging
from Crypto.Cipher import DES
from Crypto.Util.Padding import pad
from base64 import b64encode
from binascii import unhexlify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = aiohttp.ClientSession()
    coordinator = CrealityDataCoordinator(hass, session, entry.data)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, ['sensor', 'button', 'camera'])
    return True

class CrealityDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, session, config):
        self.session = session
        self.config = config
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30))

    async def _async_update_data(self):
        data = await self.fetch_data()
        if data is None:
            raise UpdateFailed("Failed to fetch data from the Creality printer.")
        return data

    async def fetch_data(self):
        uri = f"ws://{self.config['host']}:{self.config['port']}/"
        token = self.generate_token(self.config['password'])
        async with self.session.ws_connect(uri) as ws:
            await ws.send_json({"cmd": "GET_PRINT_STATUS", "token": token})
            async with asyncio.timeout(10):
                msg = await ws.receive_json()
                if msg:
                    # Try to detect printer model based on available data
                    if "model" not in msg and "printerModel" not in msg:
                        # Make an educated guess based on port
                        if self.config['port'] == 9999:
                            msg["detected_model"] = "K1 Series (FDM)"
                        elif self.config['port'] == 18188:
                            msg["detected_model"] = "Halot Series (Resin)"
                    return msg
                else:
                    _LOGGER.error("Failed to receive data")
                    return None

    def generate_token(self, password):
        # Handle empty password case
        if not password:
            password = ""
        
        key = unhexlify("6138356539643638")
        cipher = DES.new(key[:8], DES.MODE_ECB)
        padded_password = pad(password.encode(), DES.block_size)
        encrypted_password = cipher.encrypt(padded_password)
        token = b64encode(encrypted_password).decode('utf-8')
        return token

    async def send_command(self, command):
        """Send a command to the printer."""
        uri = f"ws://{self.config['host']}:{self.config['port']}/"
        token = self.generate_token(self.config['password'])
        
        try:
            async with self.session.ws_connect(uri) as ws:
                await ws.send_json({"cmd": command, "token": token})
                _LOGGER.info(f"Sent command {command} to the printer")
                response = await ws.receive()
                
                if response.type == aiohttp.WSMsgType.TEXT:
                    response_data = json.loads(response.data)
                    if response_data.get("cmd") == command and response_data.get("status") == command:
                        _LOGGER.info(f"Command {command} executed successfully.")
                    else:
                        _LOGGER.error(f"Printer responded with unexpected data: {response_data}")
                else:
                    _LOGGER.error(f"Failed to receive valid response for command {command}")
                    
        except Exception as e:
            _LOGGER.error(f"Failed to send command {command}: {e}")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Creality Control component."""
    return True


async def async_handle_ssdp_discovery(hass: HomeAssistant, discovery_info: dict) -> None:
    """Handle SSDP discovery."""
    _LOGGER.info("SSDP discovery: %s", discovery_info)
    
    # Extract host from discovery info
    host = discovery_info.get("ssdp_location", "").replace("http://", "").split("/")[0]
    if not host:
        return
    
    # Try to detect port
    port = await _detect_creality_port(hass, host)
    if not port:
        return
    
    # Create config entry
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "host": host,
            "port": port,
            "password": "",
            "name": f"Creality Printer ({host})"
        }
    )


async def async_handle_zeroconf_discovery(hass: HomeAssistant, discovery_info: dict) -> None:
    """Handle Zeroconf discovery."""
    _LOGGER.info("Zeroconf discovery: %s", discovery_info)
    
    host = discovery_info.get("host")
    port = discovery_info.get("port")
    
    if not host:
        return
    
    # If no port provided, try to detect it
    if not port:
        port = await _detect_creality_port(hass, host)
        if not port:
            return
    
    # Create config entry
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "host": host,
            "port": port,
            "password": "",
            "name": f"Creality Printer ({host})"
        }
    )


async def _detect_creality_port(hass: HomeAssistant, host: str) -> int | None:
    """Detect which port the Creality printer is using."""
    # Try common Creality ports
    ports_to_try = [9999, 18188, 8080, 80]
    
    for port in ports_to_try:
        if await _test_creality_connection(hass, host, port):
            return port
    
    return None


async def _test_creality_connection(hass: HomeAssistant, host: str, port: int) -> bool:
    """Test if a Creality printer is responding on the given host:port."""
    try:
        session = aiohttp.ClientSession()
        uri = f"ws://{host}:{port}/"
        
        async with session.ws_connect(uri, timeout=aiohttp.ClientTimeout(total=5)) as ws:
            # Send a simple test command
            await ws.send_json({"cmd": "GET_PRINT_STATUS", "token": ""})
            
            # Try to receive a response
            try:
                async with asyncio.timeout(3):
                    response = await ws.receive_json()
                    # If we get any response, it's likely a Creality printer
                    return True
            except (asyncio.TimeoutError, aiohttp.WSMsgType):
                return False
                
    except Exception:
        return False
    finally:
        await session.close()
