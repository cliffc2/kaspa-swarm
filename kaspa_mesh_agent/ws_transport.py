# kaspa_mesh_agent/ws_transport.py
"""
WebSocket fallback transport for KaspaMeshAgent
Used when Meshtastic LoRa hardware is unavailable.
Supports reliable reconnection, heartbeats, and clean message handling.
"""

import asyncio
import json
import hashlib
from typing import Dict, Optional, Callable, Awaitable
from pathlib import Path

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, ConnectionClosedOK
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class WebSocketTransport:
    def __init__(
        self,
        uri: str = "ws://localhost:8765",
        node_id: str = "unknown-node",
        max_retries: int = 8,
        reconnect_delay: int = 3,
        heartbeat_interval: int = 15,   # seconds
    ):
        self.uri = uri
        self.node_id = node_id
        self.max_retries = max_retries
        self.reconnect_delay = reconnect_delay
        self.heartbeat_interval = heartbeat_interval

        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self._message_handler: Optional[Callable[[str, Dict], Awaitable[None]]] = None
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        if not HAS_WEBSOCKETS:
            print("⚠️  WebSocket transport unavailable - run: pip install websockets")
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                self.ws = await websockets.connect(self.uri, ping_interval=20, ping_timeout=10)
                self.connected = True
                print(f"[WS] ✅ Connected to {self.uri} (node: {self.node_id})")
                self._start_heartbeat()
                return True
            except Exception as e:
                print(f"[WS] Connection attempt {attempt}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.reconnect_delay * (1 + attempt / 3))  # mild backoff

        print(f"[WS] ❌ Failed to connect after {self.max_retries} attempts")
        return False

    def _start_heartbeat(self):
        if self._heartbeat_task and not self._heartbeat_task.done():
            return
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        while self.connected and self._running:
            try:
                if self.ws:
                    await self.ws.ping()
            except Exception:
                self.connected = False
                break
            await asyncio.sleep(self.heartbeat_interval)

    async def disconnect(self):
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.connected = False
        print("[WS] Disconnected")

    async def send(self, payload: Dict, destination: str = "broadcast") -> bool:
        if not self.connected or not self.ws:
            print("[WS] Not connected - attempting reconnect...")
            await self.connect()
            if not self.connected:
                return False

        msg = {
            "node_id": self.node_id,
            "destination": destination,
            "mid": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16],
            "timestamp": asyncio.get_event_loop().time(),
            "payload": payload,
        }

        try:
            await self.ws.send(json.dumps(msg))
            return True
        except (ConnectionClosed, ConnectionClosedOK):
            print("[WS] Connection closed during send - reconnecting")
            self.connected = False
            return False
        except Exception as e:
            print(f"[WS] Send error: {e}")
            self.connected = False
            return False

    async def start_listener(self, handler: Callable[[str, Dict], Awaitable[None]]):
       