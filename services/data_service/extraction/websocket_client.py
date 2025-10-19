"""
Kite WebSocket Client for Live Market Data
Connects to Zerodha Kite WebSocket API and streams live market data
"""

import asyncio
import json
import struct
import websockets
from datetime import datetime, time
from zoneinfo import ZoneInfo
import logging
from typing import Optional, Callable, List, Dict, Any
from services.data_service.extraction.auth_client import AuthClient

KITE_WS_URL = "wss://ws.kite.trade"
IST = ZoneInfo("Asia/Kolkata")

# module logger
logger = logging.getLogger(__name__)


def is_market_open() -> tuple[bool, str]:
    """
    Check if Indian stock market is open
    
    Returns:
        tuple: (is_open: bool, reason: str)
    """
    now_ist = datetime.now(IST)
    current_day = now_ist.weekday()  # 0=Monday, 6=Sunday
    current_time = now_ist.time()
    
    # Market hours: Monday-Friday, 9:15 AM - 3:30 PM IST
    MARKET_OPEN = time(9, 15)
    MARKET_CLOSE = time(15, 30)
    
    # Check if weekend
    if current_day >= 5:  # Saturday (5) or Sunday (6)
        day_name = now_ist.strftime("%A")
        return False, f"Weekend ({day_name})"
    
    # Check if during market hours
    if current_time < MARKET_OPEN:
        return False, f"Pre-market (opens at 09:15 AM)"
    elif current_time > MARKET_CLOSE:
        return False, f"After-hours (closed at 03:30 PM)"
    else:
        return True, "Market hours (9:15 AM - 3:30 PM)"


def get_market_status_message() -> str:
    """Get detailed market status message"""
    is_open, reason = is_market_open()
    
    if is_open:
        return f"🟢 Market OPEN ({reason})"
    else:
        return f"🔴 Market CLOSED ({reason})"


class KiteWebSocketClient:
	"""
	Kite WebSocket Client for streaming live market data
	
	Features:
	- Auto-reconnection with exponential backoff
	- Binary packet parsing according to Kite API spec
	- Support for ltp, quote, and full modes
	- Token refresh from auth service
	- Callback-based tick handling
	"""
	
	def __init__(
		self,
		auth_client: Optional[AuthClient] = None,
		on_tick: Optional[Callable[[Dict], None]] = None,
		on_error: Optional[Callable[[Exception], None]] = None,
		on_connect: Optional[Callable[[], None]] = None,
		on_disconnect: Optional[Callable[[], None]] = None,
		reconnect_attempts: int = 5,
		reconnect_delay: int = 5
	):
		"""
		Initialize Kite WebSocket Client
		
		Args:
			auth_client: AuthClient instance for fetching tokens
			on_tick: Callback function for tick data
			on_error: Callback function for errors
			on_connect: Callback function on connection
			on_disconnect: Callback function on disconnection
			reconnect_attempts: Maximum reconnection attempts
			reconnect_delay: Initial reconnection delay in seconds
		"""
		self.auth_client = auth_client or AuthClient()
		self.api_key = self.auth_client.get_api_key()
		self.access_token = None
		
		self.ws = None
		self.on_tick = on_tick
		self.on_error = on_error
		self.on_connect = on_connect
		self.on_disconnect = on_disconnect
		
		self._stop = False
		self._connected = False
		self.reconnect_attempts = reconnect_attempts
		self.reconnect_delay = reconnect_delay
		
		# Lock to ensure only one coroutine calls recv() at a time
		self._recv_lock = asyncio.Lock()
		
		# Subscribed instruments
		self._subscribed_instruments: List[int] = []
		self._instrument_modes: Dict[int, str] = {}

	# Add async context manager support
	async def __aenter__(self):
		await self.connect()
		return self

	async def __aexit__(self, exc_type, exc, tb):
		await self.close()
	
	def _fetch_token(self) -> bool:
		"""
		Fetch access token from auth service
		
		Returns:
			True if token fetched successfully, False otherwise
		"""
		try:
			self.access_token = self.auth_client.get_access_token()
			if not self.access_token:
				logger.error("Failed to fetch access token from auth service")
				return False
			logger.info("Successfully fetched access token from auth service")
			return True
		except Exception as e:
			logger.error(f"Error fetching token: {e}")
			return False

	async def connect(self):
		"""Connect to Kite WebSocket with auto-retry"""
		if not self.api_key:
			raise ValueError("Kite API key not configured")
			
		# Fetch token if not available
		if not self.access_token:
			if not self._fetch_token():
				raise RuntimeError("Failed to fetch access token")
		
		# Check market status
		market_status = get_market_status_message()
		is_open, market_reason = is_market_open()
		logger.info(f"📊 {market_status}")
		
		url = f"{KITE_WS_URL}?api_key={self.api_key}&access_token={self.access_token}"
		attempt = 0
		
		while not self._stop and attempt < self.reconnect_attempts:
			try:
				# Keep reasonable ping/pong settings
				self.ws = await websockets.connect(url, ping_interval=20, ping_timeout=10)
				self._connected = True
				logger.info("✅ Connected to Kite WebSocket")
				
				# Log market status context
				if not is_open:
					logger.info(f"ℹ️  WebSocket connected, but market is {market_reason}.")
					logger.info(f"ℹ️  Data will flow when market opens (Mon-Fri 9:15 AM - 3:30 PM IST).")
				
				# Call on_connect callback
				if self.on_connect:
					try:
						self.on_connect()
					except Exception as e:
						logger.error(f"Error in on_connect callback: {e}")
				
				# Re-subscribe to instruments if any
				if self._subscribed_instruments:
					await self.subscribe(self._subscribed_instruments)
					
				# Re-apply modes
				for token, mode in self._instrument_modes.items():
					await self.set_mode(mode, [token])
				
				# Start receive loop and return (don't block the caller)
				asyncio.create_task(self.receive())
				return
				
			except Exception as e:
				attempt += 1
				if attempt >= self.reconnect_attempts:
					logger.exception("Failed to connect after %d attempts", attempt)
					raise RuntimeError(f"Failed to connect after {attempt} attempts: {e}")
					
				backoff = min(self.reconnect_delay * (2 ** attempt), 60)
				logger.warning("Connect failed (attempt %d/%d), retrying in %ds: %s", 
							 attempt, self.reconnect_attempts, backoff, e)
				await asyncio.sleep(backoff)

	async def send(self, message: dict):
		"""Send message to WebSocket"""
		if not self.ws or not self._connected:
			raise RuntimeError("WebSocket is not connected")
		await self.ws.send(json.dumps(message))
		logger.debug(f"Sent message: {message}")

	async def subscribe(self, instrument_tokens: List[int]):
		"""
		Subscribe to instruments
		
		Args:
			instrument_tokens: List of instrument tokens to subscribe
		"""
		# Store subscriptions for reconnection
		for token in instrument_tokens:
			if token not in self._subscribed_instruments:
				self._subscribed_instruments.append(token)
		
		msg = {"a": "subscribe", "v": instrument_tokens}
		await self.send(msg)
		logger.info(f"Subscribed to {len(instrument_tokens)} instruments")

	async def unsubscribe(self, instrument_tokens: List[int]):
		"""
		Unsubscribe from instruments
		
		Args:
			instrument_tokens: List of instrument tokens to unsubscribe
		"""
		# Remove from subscriptions
		for token in instrument_tokens:
			if token in self._subscribed_instruments:
				self._subscribed_instruments.remove(token)
			if token in self._instrument_modes:
				del self._instrument_modes[token]
		
		msg = {"a": "unsubscribe", "v": instrument_tokens}
		await self.send(msg)
		logger.info(f"Unsubscribed from {len(instrument_tokens)} instruments")

	async def set_mode(self, mode: str, instrument_tokens: List[int]):
		"""
		Set mode for instruments
		
		Args:
			mode: Mode - 'ltp', 'quote', or 'full'
			instrument_tokens: List of instrument tokens
		"""
		if mode not in ['ltp', 'quote', 'full']:
			raise ValueError(f"Invalid mode: {mode}. Must be 'ltp', 'quote', or 'full'")
		
		# Store modes for reconnection
		for token in instrument_tokens:
			self._instrument_modes[token] = mode
		
		# Kite expects [mode, [tokens]]
		msg = {"a": "mode", "v": [mode, instrument_tokens]}
		await self.send(msg)
		logger.info(f"Set mode '{mode}' for {len(instrument_tokens)} instruments")

	async def close(self):
		"""Close WebSocket connection gracefully"""
		self._stop = True
		self._connected = False
		
		if self.ws:
			try:
				await self.ws.close()
			except Exception:
				logger.exception("Error while closing websocket")
			self.ws = None
			
		if self.on_disconnect:
			try:
				self.on_disconnect()
			except Exception as e:
				logger.error(f"Error in on_disconnect callback: {e}")
				
		logger.info("WebSocket closed")

	async def receive(self):
		"""Keep receiving messages until stopped or connection errors"""
		while not self._stop:
			if not self.ws:
				await asyncio.sleep(1)
				continue
				
			try:
				# Ensure single receiver at a time
				async with self._recv_lock:
					msg = await self.ws.recv()
					
			except websockets.ConnectionClosed as e:
				logger.warning(f"Connection closed: {e}")
				self._connected = False
				
				if self.on_disconnect:
					try:
						self.on_disconnect()
					except Exception as e:
						logger.error(f"Error in on_disconnect callback: {e}")
				
				# Attempt reconnect
				if not self._stop:
					await asyncio.sleep(self.reconnect_delay)
					try:
						# Refresh token before reconnecting
						self._fetch_token()
						await self.connect()
						return  # Exit this receive loop, connect() will spawn a new one
					except Exception as e:
						logger.error(f"Reconnection failed: {e}")
						if self.on_error:
							try:
								self.on_error(e)
							except Exception as cb_error:
								logger.error(f"Error in on_error callback: {cb_error}")
				return
				
			except Exception as e:
				logger.exception(f"Error in receive loop: {e}")
				if self.on_error:
					try:
						self.on_error(e)
					except Exception as cb_error:
						logger.error(f"Error in on_error callback: {cb_error}")
				await asyncio.sleep(1)
				continue

			# Handle message
			if isinstance(msg, (bytes, bytearray)):
				try:
					self.handle_binary(msg)
				except Exception as e:
					logger.exception(f"Failed to handle binary message: {e}")
					if self.on_error:
						try:
							self.on_error(e)
						except Exception as cb_error:
							logger.error(f"Error in on_error callback: {cb_error}")
			else:
				try:
					self.handle_text(msg)
				except Exception as e:
					logger.exception(f"Failed to handle text message: {e}")

	def handle_text(self, msg: str):
		"""Handle text messages (JSON) from WebSocket"""
		try:
			data = json.loads(msg)
			msg_type = data.get("type")
			
			if msg_type == "error":
				logger.error(f"WebSocket error: {data.get('data')}")
				if self.on_error:
					self.on_error(Exception(data.get('data')))
					
			elif msg_type == "message":
				logger.info(f"WebSocket message: {data.get('data')}")
				
			elif msg_type == "order":
				logger.info(f"Order update: {data.get('data')}")
				# You can add order update callback here
				
			else:
				logger.debug(f"Text message: {json.dumps(data, indent=2)}")
				
		except json.JSONDecodeError:
			# Heartbeat or invalid JSON
			logger.debug("Heartbeat or non-JSON text received")

	def handle_binary(self, msg: bytes):
		"""
		Handle binary messages from WebSocket
		Parse according to Kite API specification
		"""
		if len(msg) < 2:
			# Heartbeat
			logger.debug("Heartbeat received")
			return

		# First 2 bytes = number of packets
		num_packets = struct.unpack("!H", msg[0:2])[0]
		offset = 2
		
		for _ in range(num_packets):
			if offset + 2 > len(msg):
				logger.warning("Incomplete packet header")
				break
				
			# Next 2 bytes = packet length
			packet_len = struct.unpack("!H", msg[offset:offset + 2])[0]
			offset += 2
			
			if offset + packet_len > len(msg):
				logger.warning("Incomplete packet data")
				break
				
			# Extract packet
			packet = msg[offset:offset + packet_len]
			offset += packet_len
			
			# Parse packet
			try:
				data = self.parse_packet(packet)
				if data:
					self.emit_tick(data)
			except Exception as e:
				logger.error(f"Error parsing packet: {e}")

	def parse_packet(self, packet: bytes) -> Optional[Dict[str, Any]]:
		"""
		Parse a single packet according to Kite API specification
		
		Returns:
			Dict with parsed tick data or None if invalid
		"""
		length = len(packet)
		
		if length < 4:
			logger.warning(f"Packet too short: {length} bytes")
			return None
		
		try:
			# First 4 bytes = instrument token
			instrument_token = struct.unpack("!I", packet[0:4])[0]
			
			# LTP mode - 8 bytes total
			if length == 8:
				last_price = struct.unpack("!I", packet[4:8])[0] / 100.0
				return {
					"instrument_token": instrument_token,
					"last_price": last_price,
					"mode": "ltp",
					"timestamp": datetime.utcnow(),
				}
			
			# Quote mode - 44 bytes total
			elif length == 44:
				fields = struct.unpack("!11I", packet[:44])
				return {
					"instrument_token": fields[0],
					"last_price": fields[1] / 100.0,
					"last_quantity": fields[2],
					"average_price": fields[3] / 100.0,
					"volume": fields[4],
					"buy_quantity": fields[5],
					"sell_quantity": fields[6],
					"open": fields[7] / 100.0,
					"high": fields[8] / 100.0,
					"low": fields[9] / 100.0,
					"close": fields[10] / 100.0,
					"mode": "quote",
					"timestamp": datetime.utcnow(),
				}
			
			# Full mode - 184 bytes total (includes market depth)
			elif length == 184:
				# Parse main fields (44 bytes)
				fields = struct.unpack("!11I", packet[:44])
				
				# Parse additional fields
				ltt = struct.unpack("!I", packet[44:48])[0]  # Last traded timestamp
				oi = struct.unpack("!I", packet[48:52])[0]
				oi_day_high = struct.unpack("!I", packet[52:56])[0]
				oi_day_low = struct.unpack("!I", packet[56:60])[0]
				exchange_ts = struct.unpack("!I", packet[60:64])[0]
				
				# Parse market depth (64 - 184 = 120 bytes)
				# 5 bid entries + 5 offer entries, 12 bytes each
				depth = {"buy": [], "sell": []}
				
				# Parse bid entries (64 - 124)
				for i in range(5):
					start = 64 + (i * 12)
					qty, price, orders = struct.unpack("!IIH", packet[start:start+10])
					depth["buy"].append({
						"quantity": qty,
						"price": price / 100.0,
						"orders": orders
					})
				
				# Parse offer entries (124 - 184)
				for i in range(5):
					start = 124 + (i * 12)
					qty, price, orders = struct.unpack("!IIH", packet[start:start+10])
					depth["sell"].append({
						"quantity": qty,
						"price": price / 100.0,
						"orders": orders
					})
				
				return {
					"instrument_token": fields[0],
					"last_price": fields[1] / 100.0,
					"last_quantity": fields[2],
					"average_price": fields[3] / 100.0,
					"volume": fields[4],
					"buy_quantity": fields[5],
					"sell_quantity": fields[6],
					"open": fields[7] / 100.0,
					"high": fields[8] / 100.0,
					"low": fields[9] / 100.0,
					"close": fields[10] / 100.0,
					"last_traded_timestamp": datetime.fromtimestamp(ltt) if ltt > 0 else None,
					"oi": oi,
					"oi_day_high": oi_day_high,
					"oi_day_low": oi_day_low,
					"exchange_timestamp": datetime.fromtimestamp(exchange_ts) if exchange_ts > 0 else None,
					"depth": depth,
					"mode": "full",
					"timestamp": datetime.utcnow(),
				}
			
			else:
				logger.warning(f"Unknown packet length: {length} bytes")
				return {
					"instrument_token": instrument_token,
					"raw_length": length,
					"mode": "unknown"
				}
				
		except struct.error as e:
			logger.error(f"Struct unpacking error: {e}")
			return None
		except Exception as e:
			logger.error(f"Unexpected error parsing packet: {e}")
			return None

	def emit_tick(self, data: Dict[str, Any]):
		"""
		Emit tick data to callback
		
		Args:
			data: Parsed tick data
		"""
		if self.on_tick:
			try:
				self.on_tick(data)
			except Exception as e:
				logger.exception(f"on_tick callback raised: {e}")
		else:
			logger.debug(f"TICK → {data}")

