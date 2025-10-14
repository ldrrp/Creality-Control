"""Creality Control integration for Home Assistant."""
import aiohttp
import asyncio
import json
import random
import time
from typing import Any, Dict, Optional
from enum import Enum

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
            self.session = await async_get_clientsession(self.coordinator.hass)
            
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
            
            # Update coordinator data
            self.coordinator.data = data
            self.coordinator.async_update_listeners()
            
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
        return self.data or {}
        
    async def _poll_data(self) -> Dict[str, Any]:
        """Fallback polling method when WebSocket is unavailable."""
        try:
            session = await async_get_clientsession(self.hass)
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
    await hass.config_entries.async_forward_entry_setups(entry, ['sensor', 'button', 'camera'])
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_unload()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ['sensor', 'button', 'camera'])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

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
        session = await async_get_clientsession(hass)
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