"""Creality Control integration for Home Assistant."""
import aiohttp
import asyncio
import json
import random
import time
from typing import Any, Dict, Optional
from enum import Enum

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant import config_entries
from datetime import timedelta
import logging

from Crypto.Cipher import DES
from Crypto.Util.Padding import pad
from base64 import b64encode
from binascii import unhexlify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Endpoint URL for sending data to stats
ENDPOINT_URL = "https://faas-nyc1-2ef2e6cc.doserverless.co/api/v1/web/fn-21a02825-e6a2-4937-96fc-5aa2163df723/v1/creality-control"

class ConnectionState(Enum):
    """WebSocket connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STALE = "stale"
    RECONNECTING = "reconnecting"

class CrealityWebSocketClient:
    """Robust WebSocket client with reconnection and heartbeat."""
    
    def __init__(self, host: str, port: int, password: str, coordinator: 'CrealityDataCoordinator'):
        self.host = host
        self.port = port
        self.password = password
        self.coordinator = coordinator
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.state = ConnectionState.DISCONNECTED
        self.last_message_time = 0.0
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.base_reconnect_delay = 1.0
        self.max_reconnect_delay = 60.0
        self.heartbeat_interval = 20.0
        self.receive_timeout = 60.0
        self.stale_threshold = 90.0
        self._task: Optional[asyncio.Task] = None
        self._shutdown = False
        
    async def start(self) -> None:
        """Start the WebSocket client."""
        if self._task and not self._task.done():
            return
            
        self._shutdown = False
        self._task = asyncio.create_task(self._run())
        
    async def stop(self) -> None:
        """Stop the WebSocket client."""
        self._shutdown = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._disconnect()
        
    async def send_command(self, command: str) -> bool:
        """Send a command to the printer."""
        if self.state != ConnectionState.CONNECTED or not self.ws or self.ws.closed:
            _LOGGER.warning(f"Cannot send command {command}: WebSocket not connected")
            return False
            
        try:
            token = self._generate_token(self.password)
            await self.ws.send_json({"cmd": command, "token": token})
            _LOGGER.info(f"Sent command {command} to printer")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to send command {command}: {e}")
            return False
    
    async def send_json(self, payload: dict) -> bool:
        """Send a JSON payload to the printer."""
        if self.state != ConnectionState.CONNECTED or not self.ws or self.ws.closed:
            _LOGGER.warning("Cannot send JSON payload: WebSocket not connected")
            return False
            
        try:
            await self.ws.send_json(payload)
            _LOGGER.debug(f"Sent JSON payload: {payload}")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to send JSON payload: {e}")
            return False
            
    def _generate_token(self, password: str) -> str:
        """Generate authentication token."""
        if not password:
            password = ""
        
        key = unhexlify("6138356539643638")
        cipher = DES.new(key[:8], DES.MODE_ECB)
        padded_password = pad(password.encode(), DES.block_size)
        encrypted_password = cipher.encrypt(padded_password)
        token = b64encode(encrypted_password).decode('utf-8')
        return token
        
    async def _run(self) -> None:
        """Main WebSocket loop with reconnection logic."""
        while not self._shutdown:
            try:
                await self._connect()
                await self._message_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"WebSocket error: {e}")
                await self._handle_connection_error()
                
    async def _connect(self) -> None:
        """Establish WebSocket connection."""
        if self.state == ConnectionState.CONNECTED:
            return
            
        self._set_state(ConnectionState.CONNECTING)
        
        if not self.session or self.session.closed:
            self.session = async_get_clientsession(self.coordinator.hass)
            
        uri = f"ws://{self.host}:{self.port}/"
        timeout = aiohttp.ClientTimeout(total=15, connect=10)
        
        try:
            self.ws = await self.session.ws_connect(
                uri,
                timeout=timeout,
                heartbeat=20,  # Send ping every 20 seconds
                receive_timeout=self.receive_timeout
            )
            self._set_state(ConnectionState.CONNECTED)
            self.reconnect_attempts = 0
            self.last_message_time = time.time()
            _LOGGER.info(f"Connected to Creality printer at {self.host}:{self.port}")
            
        except (aiohttp.ClientConnectorError, aiohttp.WSServerHandshakeError) as e:
            _LOGGER.warning(f"Connection failed: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected connection error: {e}")
            raise
            
    async def _message_loop(self) -> None:
        """Handle incoming messages and heartbeat."""
        if not self.ws:
            return
            
        try:
            # Send initial status request
            await self.send_command("GET_PRINT_STATUS")
            
            async for msg in self.ws:
                if self._shutdown:
                    break
                    
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_message(data)
                    except json.JSONDecodeError as e:
                        _LOGGER.warning(f"Invalid JSON received: {e}")
                        continue
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.error(f"WebSocket error: {self.ws.exception()}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    _LOGGER.info("WebSocket connection closed")
                    break
                elif msg.type == aiohttp.WSMsgType.PING:
                    _LOGGER.debug("Received ping")
                elif msg.type == aiohttp.WSMsgType.PONG:
                    _LOGGER.debug("Received pong")
                    
        except asyncio.TimeoutError:
            _LOGGER.warning("WebSocket receive timeout")
        except Exception as e:
            _LOGGER.error(f"Message loop error: {e}")
            raise
            
    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket message."""
        self.last_message_time = time.time()
        
        # Update coordinator data
        if data:
            # Try to detect printer model if not present
            if "model" not in data and "printerModel" not in data:
                if self.port == 9999:
                    data["detected_model"] = "K1 Series (FDM)"
                elif self.port == 18188:
                    data["detected_model"] = "Halot Series (Resin)"
            
            # Merge with existing data instead of replacing
            if self.coordinator.data:
                # Merge new data with existing data
                self.coordinator.data.update(data)
            else:
                # First message - set the full dataset
                self.coordinator.data = data
                _LOGGER.info("🚀 First WebSocket message - sending raw data to endpoint")
                _LOGGER.info(f"Data keys: {list(data.keys())}")
                await self._send_raw_data_to_endpoint(data)
            
            self.coordinator.last_update_success = True
            self.coordinator.last_update_time = time.time()
            self.coordinator.async_update_listeners()
            
            # Debug logging for key values
            _LOGGER.debug(f"WebSocket data received: {len(data)} fields, total data: {len(self.coordinator.data)} fields")
            if "nozzleTemp" in data:
                _LOGGER.debug(f"Nozzle temp: {data['nozzleTemp']}")
            if "bedTemp0" in data:
                _LOGGER.debug(f"Bed temp: {data['bedTemp0']}")
            if "printProgress" in data:
                _LOGGER.debug(f"Progress: {data['printProgress']}")
    
    async def _send_raw_data_to_endpoint(self, data: Dict[str, Any]) -> None:
        """Send raw websocket data to the endpoint for Stats upload."""
        try:
            # Send the raw websocket data directly
            payload = {
                "data": data
            }
            
            _LOGGER.info(f"📤 Sending raw websocket data to endpoint: {len(data)} fields")
            _LOGGER.info(f"📤 Endpoint URL: {ENDPOINT_URL}")
            _LOGGER.info(f"📤 Sample data keys: {list(data.keys())[:10]}...")  # Show first 10 keys
            
            # Send to endpoint
            session = async_get_clientsession(self.coordinator.hass)
            _LOGGER.info("📤 Making HTTP POST request...")
            
            async with session.post(
                ENDPOINT_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                _LOGGER.info(f"📤 Response received - Status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    _LOGGER.info(f"✅ Successfully sent raw printer data to endpoint. Response: {result}")
                else:
                    response_text = await response.text()
                    _LOGGER.warning(f"❌ Endpoint returned status {response.status}: {response_text}")
                    
        except Exception as e:
            _LOGGER.error(f"❌ Failed to send raw data to endpoint: {e}")
            _LOGGER.error(f"❌ Exception type: {type(e).__name__}")
            import traceback
            _LOGGER.error(f"❌ Traceback: {traceback.format_exc()}")
    
    async def force_send_data_to_endpoint(self) -> None:
        """Force send current data to endpoint (for testing)."""
        if self.coordinator.data:
            _LOGGER.info("🔧 Force sending data to endpoint for testing")
            await self._send_raw_data_to_endpoint(self.coordinator.data)
        else:
            _LOGGER.warning("No data available to send")
            
    async def _handle_connection_error(self) -> None:
        """Handle connection errors with exponential backoff."""
        await self._disconnect()
        
        if self._shutdown:
            return
            
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            _LOGGER.error("Max reconnection attempts reached")
            self._set_state(ConnectionState.DISCONNECTED)
            return
            
        self._set_state(ConnectionState.RECONNECTING)
        self.reconnect_attempts += 1
        
        # Exponential backoff with jitter
        delay = min(
            self.base_reconnect_delay * (2 ** self.reconnect_attempts),
            self.max_reconnect_delay
        )
        jitter = random.uniform(0.1, 0.5) * delay
        total_delay = delay + jitter
        
        _LOGGER.info(f"Reconnecting in {total_delay:.1f}s (attempt {self.reconnect_attempts})")
        await asyncio.sleep(total_delay)
        
    async def _disconnect(self) -> None:
        """Disconnect WebSocket."""
        if self.ws and not self.ws.closed:
            await self.ws.close()
        self._set_state(ConnectionState.DISCONNECTED)
        
    def _set_state(self, new_state: ConnectionState) -> None:
        """Update connection state with logging."""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            _LOGGER.info(f"Connection state: {old_state.value} -> {new_state.value}")
            
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        if self.state != ConnectionState.CONNECTED:
            return False
            
        current_time = time.time()
        time_since_last_message = current_time - self.last_message_time
        
        if time_since_last_message > self.stale_threshold:
            if self.state != ConnectionState.STALE:
                self._set_state(ConnectionState.STALE)
                _LOGGER.warning(f"Connection stale: no data for {time_since_last_message:.1f}s")
            return False
            
        return True

class CrealityDataCoordinator(DataUpdateCoordinator):
    """Coordinator for Creality printer data with robust WebSocket connection."""
    
    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30)
        )
        self.config = config
        self.ws_client: Optional[CrealityWebSocketClient] = None
        self._setup_task: Optional[asyncio.Task] = None
        
    async def async_config_entry_first_refresh(self) -> None:
        """Initialize WebSocket connection on first refresh."""
        await super().async_config_entry_first_refresh()
        await self._start_websocket()
        
    async def _start_websocket(self) -> None:
        """Start WebSocket client."""
        if self.ws_client:
            return
            
        self.ws_client = CrealityWebSocketClient(
            self.config['host'],
            self.config['port'],
            self.config['password'],
            self
        )
        
        self._setup_task = asyncio.create_task(self.ws_client.start())
        
    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data from WebSocket."""
        if not self.ws_client or not self.ws_client.is_healthy():
            # If WebSocket is not healthy, try to get data via polling
            return await self._poll_data()
        
        # If WebSocket is healthy, return current data (it's updated in real-time)
        if self.data:
            return self.data
        
        # If no data yet, try polling once
        return await self._poll_data()
        
    async def _poll_data(self) -> Dict[str, Any]:
        """Fallback polling method when WebSocket is unavailable."""
        try:
            session = async_get_clientsession(self.hass)
            uri = f"ws://{self.config['host']}:{self.config['port']}/"
            token = self._generate_token(self.config['password'])
            
            async with session.ws_connect(uri, timeout=aiohttp.ClientTimeout(total=10)) as ws:
                await ws.send_json({"cmd": "GET_PRINT_STATUS", "token": token})
                async with asyncio.timeout(10):
                    msg = await ws.receive_json()
                    if msg:
                        # Try to detect printer model if not present
                        if "model" not in msg and "printerModel" not in msg:
                            if self.config['port'] == 9999:
                                msg["detected_model"] = "K1 Series (FDM)"
                            elif self.config['port'] == 18188:
                                msg["detected_model"] = "Halot Series (Resin)"
                        return msg
        except Exception as e:
            _LOGGER.error(f"Polling failed: {e}")
            raise UpdateFailed(f"Failed to fetch data: {e}")
            
    def _generate_token(self, password: str) -> str:
        """Generate authentication token."""
        if not password:
            password = ""
        
        key = unhexlify("6138356539643638")
        cipher = DES.new(key[:8], DES.MODE_ECB)
        padded_password = pad(password.encode(), DES.block_size)
        encrypted_password = cipher.encrypt(padded_password)
        token = b64encode(encrypted_password).decode('utf-8')
        return token
        
    async def send_command(self, command: str) -> bool:
        """Send a command to the printer."""
        if not self.ws_client:
            _LOGGER.warning("WebSocket client not available")
            return False
        return await self.ws_client.send_command(command)
    
    async def send_temp_command(self, temp_type: str, temperature: int) -> bool:
        """Send a temperature control command to the printer."""
        if not self.ws_client:
            _LOGGER.warning("WebSocket client not available")
            return False
        
        if temp_type == "nozzle":
            command = {"method": "set", "params": {"nozzleTempControl": temperature}}
        elif temp_type == "bed":
            command = {"method": "set", "params": {"bedTempControl": {"num": 0, "val": temperature}}}
        else:
            _LOGGER.error(f"Invalid temperature type: {temp_type}")
            return False
        
        return await self.ws_client.send_json(command)
    
    async def send_websocket_command(self, command: dict) -> bool:
        """Send a WebSocket JSON command to the printer."""
        if not self.ws_client:
            _LOGGER.warning("WebSocket client not available")
            return False
        return await self.ws_client.send_json(command)
        
    async def async_unload(self) -> None:
        """Clean up resources on unload."""
        if self.ws_client:
            await self.ws_client.stop()
        if self._setup_task and not self._setup_task.done():
            self._setup_task.cancel()

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    coordinator = CrealityDataCoordinator(hass, entry.data)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    
    # Use modern async_forward_entry_setups
    await hass.config_entries.async_forward_entry_setups(entry, ['sensor', 'button', 'camera', 'number', 'switch'])
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_unload()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ['sensor', 'button', 'camera', 'number', 'switch'])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Creality Control component."""
    return True

@callback
def async_register_static_paths(hass: HomeAssistant) -> None:
    """Register static paths for the integration."""
    import os
    # Register the images directory for serving product images
    images_path = os.path.join(hass.config.config_dir, "custom_components", DOMAIN, "images")
    _LOGGER.info(f"Registering static path: /{DOMAIN}/images -> {images_path}")
    _LOGGER.info(f"Images directory exists: {os.path.exists(images_path)}")
    
    # Use the correct Home Assistant API for static paths
    hass.http.register_static_path(
        f"/{DOMAIN}/images",
        images_path,
        cache_headers=False
    )

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
        session = async_get_clientsession(hass)
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