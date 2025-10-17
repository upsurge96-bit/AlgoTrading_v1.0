# kite_ws_client.py
import asyncio
import json
import struct
import websockets
from datetime import datetime
import logging

KITE_WS_URL = "wss://ws.kite.trade"

# module logger
logger = logging.getLogger(__name__)

class KiteWebSocketClient:
	def __init__(self, api_key: str, access_token: str, on_tick=None, reconnect_attempts: int = 5):
		self.api_key = api_key
		self.access_token = access_token
		self.ws = None
		self.on_tick = on_tick  # ✅ Callback for tick data
		self._stop = False
		self.reconnect_attempts = reconnect_attempts
		# Lock to ensure only one coroutine calls recv() at a time
		self._recv_lock = asyncio.Lock()

	# Add async context manager support
	async def __aenter__(self):
		await self.connect()
		return self

	async def __aexit__(self, exc_type, exc, tb):
		await self.close()

	async def connect(self):
		url = f"{KITE_WS_URL}?api_key={self.api_key}&access_token={self.access_token}"
		attempt = 0
		while not self._stop:
			try:
				# Keep reasonable ping/pong settings
				self.ws = await websockets.connect(url, ping_interval=20, ping_timeout=10)
				logger.info("Connected to Kite WebSocket")
				# Start receive loop and return (don't block the caller)
				asyncio.create_task(self.receive())
				return
			except Exception as e:
				attempt += 1
				if attempt > self.reconnect_attempts:
					logger.exception("Failed to connect after %d attempts", attempt)
					raise RuntimeError(f"Failed to connect after {attempt} attempts: {e}")
				backoff = min(2 ** attempt, 30)
				logger.warning("Connect failed (attempt %d), retrying in %ds: %s", attempt, backoff, e)
				await asyncio.sleep(backoff)

	async def send(self, message: dict):
		if not self.ws:
			raise RuntimeError("WebSocket is not connected")
		await self.ws.send(json.dumps(message))

	async def subscribe(self, instrument_tokens: list[int]):
		# ensure list of ints
		msg = {"a": "subscribe", "v": instrument_tokens}
		await self.send(msg)
		logger.info("Subscribed to %s", instrument_tokens)

	async def set_mode(self, mode: str, instrument_tokens: list[int]):
		# Kite expects [mode, [tokens]]
		msg = {"a": "mode", "v": [mode, instrument_tokens]}
		await self.send(msg)
		logger.info("Set mode '%s' for %s", mode, instrument_tokens)

	# Add a stop/close for graceful shutdown
	async def close(self):
		self._stop = True
		if self.ws:
			try:
				await self.ws.close()
			except Exception:
				logger.exception("Error while closing websocket")
			self.ws = None
		logger.info("WebSocket closed")

	async def receive(self):
		# Keep receiving until stopped or connection errors
		while not self._stop:
			if not self.ws:
				await asyncio.sleep(1)
				continue
			try:
				# Ensure single receiver at a time
				async with self._recv_lock:
					msg = await self.ws.recv()
			except websockets.ConnectionClosed as e:
				logger.warning("Connection closed: %s", e)
				# attempt reconnect: connect() will spawn a new receive task.
				# To avoid duplicate concurrent receive() calls on the same websocket,
				# return from this receive loop after connect() completes so only the
				# newly-created task continues receiving.
				await asyncio.sleep(1)
				await self.connect()
				return
			except Exception as e:
				logger.exception("Error in receive loop: %s", e)
				await asyncio.sleep(1)
				continue

			if isinstance(msg, (bytes, bytearray)):
				try:
					self.handle_binary(msg)
				except Exception as e:
					logger.exception("Failed to handle binary message: %s", e)
			else:
				try:
					self.handle_text(msg)
				except Exception as e:
					logger.exception("Failed to handle text message: %s", e)

	def handle_text(self, msg: str):
		try:
			data = json.loads(msg)
			logger.debug("Text message: %s", json.dumps(data, indent=2))
		except json.JSONDecodeError:
			logger.debug("Heartbeat received")

	def handle_binary(self, msg: bytes):
		if len(msg) < 2:
			logger.debug("Heartbeat received")
			return

		num_packets = struct.unpack("!H", msg[0:2])[0]
		offset = 2
		for _ in range(num_packets):
			if offset + 2 > len(msg):
				break
			packet_len = struct.unpack("!H", msg[offset:offset + 2])[0]
			offset += 2
			if offset + packet_len > len(msg):
				break
			packet = msg[offset:offset + packet_len]
			offset += packet_len
			data = self.parse_packet(packet)
			self.emit_tick(data)

	def parse_packet(self, packet: bytes):
		# Safely parse packet; guard against unexpected lengths
		try:
			token = struct.unpack("!i", packet[0:4])[0]
		except struct.error:
			return {"raw": True, "length": len(packet)}

		length = len(packet)
		# expected 11 ints (44 bytes) for full packet; be defensive
		if length >= 44:
			try:
				fields = struct.unpack("!11i", packet[:44])
				return {
					"token": fields[0],
					"ltp": fields[1] / 100,
					"open": fields[7] / 100,
					"high": fields[8] / 100,
					"low": fields[9] / 100,
					"close": fields[10] / 100,
					"timestamp": datetime.now().isoformat()
				}
			except struct.error:
				logger.debug("Unexpected packet structure, length=%d", length)
				# fallback: return minimal info
				return {"token": token, "raw_length": length}
		return {"token": token, "raw_length": length}

	def emit_tick(self, data: dict):
		"""Either print or send tick to callback"""
		if self.on_tick:
			try:
				# Send tick to another module via callback
				self.on_tick(data)
			except Exception as e:
				logger.exception("on_tick callback raised: %s", e)
		else:
			logger.info("TICK → %s", data)
