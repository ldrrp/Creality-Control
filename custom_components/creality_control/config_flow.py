import voluptuous as vol
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from aiohttp import ClientSession, ClientError, ClientTimeout
import asyncio
import logging
from Crypto.Cipher import DES
from Crypto.Util.Padding import pad
from base64 import b64encode
from binascii import unhexlify
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class CrealityControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Creality Control."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            valid = await self._test_connection(
                user_input["host"], user_input["port"], user_input["password"]
            )
            if valid:
                return self.async_create_entry(title="Creality Control", data=user_input)
            else:
                errors["base"] = "cannot_connect" if valid is None else "invalid_password"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): cv.string,
                vol.Required("port", default=9999): cv.port,
                vol.Optional("password", default=""): cv.string,
            }),
            description_placeholders={
                "port_note": "K1SE and newer printers use port 9999. Older printers (Halot series) may use port 18188."
            },
            errors=errors,
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle SSDP discovery."""
        _LOGGER.info("SSDP discovery: %s", discovery_info)
        
        # Extract host from discovery info
        host = discovery_info.get("ssdp_location", "").replace("http://", "").split("/")[0]
        if not host:
            return self.async_abort(reason="no_host")
        
        # Try to detect port
        port = await self._detect_creality_port(host)
        if not port:
            return self.async_abort(reason="no_port")
        
        # Check if already configured
        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()
        
        return self.async_create_entry(
            title=f"Creality Printer ({host})",
            data={
                "host": host,
                "port": port,
                "password": "",
            }
        )

    async def async_step_zeroconf(self, discovery_info):
        """Handle Zeroconf discovery."""
        _LOGGER.info("Zeroconf discovery: %s", discovery_info)
        
        host = discovery_info.get("host")
        port = discovery_info.get("port")
        
        if not host:
            return self.async_abort(reason="no_host")
        
        # If no port provided, try to detect it
        if not port:
            port = await self._detect_creality_port(host)
            if not port:
                return self.async_abort(reason="no_port")
        
        # Check if already configured
        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()
        
        return self.async_create_entry(
            title=f"Creality Printer ({host})",
            data={
                "host": host,
                "port": port,
                "password": "",
            }
        )

    async def _detect_creality_port(self, host: str) -> int | None:
        """Detect which port the Creality printer is using."""
        # Try common Creality ports
        ports_to_try = [9999, 18188, 8080, 80]
        
        for port in ports_to_try:
            if await self._test_creality_connection(host, port):
                return port
        
        return None

    async def _test_creality_connection(self, host: str, port: int) -> bool:
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

    async def _test_connection(self, host, port, password):
        """Test connection to the Creality printer."""
        uri = f"ws://{host}:{port}/"
        token = self.generate_token(password)
        try:
            async with ClientSession() as session:
                async with session.ws_connect(uri) as ws:
                    await ws.send_json({"cmd": "GET_PRINT_STATUS", "token": token})
                    async with async_timeout.timeout(10):
                        response = await ws.receive_json()
                        if "printStatus" in response and response["printStatus"] == "TOKEN_ERROR":
                            return False  # Token is invalid
                        return True  # Assuming any response with printStatus not TOKEN_ERROR is valid
        except Exception as e:
            return None  # Unable to connect
        return None  # In case the connection could not be established or an unexpected error occurred

    def generate_token(self, password):
        """Generate a token based on the password."""
        # Handle empty password case
        if not password:
            password = ""
        
        key = unhexlify("6138356539643638")
        cipher = DES.new(key[:8], DES.MODE_ECB)
        padded_password = pad(password.encode(), DES.block_size)
        encrypted_password = cipher.encrypt(padded_password)
        token = b64encode(encrypted_password).decode('utf-8')
        return token
