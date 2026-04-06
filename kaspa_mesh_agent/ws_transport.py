"""
ws_transport.py - WebSocket fallback transport for KaspaMeshAgent
Used when Meshtastic LoRa hardware is unavailable.
"""

import asyncio
import json
import hashlib
import base64
from typing import Dict, Optional, Callable, Awaitable
from pathlib import Path

try:
    import websockets

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class WebSocketTransport:
    def __init__(
        self,
        uri: str = "ws://localhost:8765",
        node_id: str = "",
        max_retries: int = 5,
        reconnect_delay: int = 5,
    ):
        self.uri = uri
        self.node_id = node_id
        self.max_retries = max_retries
        self.reconnect_delay = reconnect_delay
        self.ws = None
        self.connected = False
        self._message_handler: Optional[Callable] = None
        self._running = False

    async def connect(self) -> bool:
        if not HAS_WEBSOCKETS:
            print("WebSocket transport unavailable - install websockets package")
            return False

        for attempt in range(self.max_retries):
            try:
                self.ws = await websockets.connect(self.uri)
                self.connected = True
                print(f"[WS] Connected to {self.uri}")
                return True
            except Exception as e:
                print(f"[WS] Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.reconnect_delay)

        print("[WS] Failed to connect after max retries")
        return False

    async def disconnect(self):
        if self.ws:
            await self.ws.close()
            self.connected = False
            print("[WS] Disconnected")

    async def send(self, payload: Dict, destination: str = "broadcast") -> bool:
        if not self.connected or not self.ws:
            print("[WS] Not connected - cannot send")
            return False

        msg = {
            "node_id": self.node_id,
            "destination": destination,
            "mid": hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:12],
            "payload": payload,
        }

        try:
            await self.ws.send(json.dumps(msg))
            return True
        except Exception as e:
            print(f"[WS] Send failed: {e}")
            self.connected = False
            return False

    async def start_listener(self, handler: Callable[[str, Dict], Awaitable[None]]):
        self._message_handler = handler
        self._running = True

        while self._running:
            if not self.connected:
                await self.connect()
                await asyncio.sleep(1)
                continue

            try:
                raw = await asyncio.wait_for(self.ws.recv(), timeout=30)
                msg = json.loads(raw)
                mid = msg.get("mid", "unknown")
                payload = msg.get("payload", {})

                if self._message_handler:
                    await self._message_handler(mid, payload)

            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                print("[WS] Connection closed - reconnecting")
                self.connected = False
                await asyncio.sleep(self.reconnect_delay)
            except Exception as e:
                print(f"[WS] Error: {e}")
                await asyncio.sleep(self.reconnect_delay)

    def stop_listener(self):
        self._running = False
        print("[WS] Listener stopped")
