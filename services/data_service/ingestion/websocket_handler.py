import asyncio
import json
import struct
import websockets
from datetime import datetime

KITE_WS_URL = "wss://ws.kite.trade"


class KiteWebSocketClient:
    def __init__(self, api_key: str, access_token: str):
        self.api_key = api_key
        self.access_token = access_token
        self.ws = None

    async def connect(self):
        url = f"{KITE_WS_URL}?api_key={self.api_key}&access_token={self.access_token}"
        self.ws = await websockets.connect(url)
        print("✅ Connected to Kite WebSocket")
        await asyncio.gather(self.receive())

    async def send(self, message: dict):
        await self.ws.send(json.dumps(message))

    async def subscribe(self, instrument_tokens: list[int]):
        msg = {"a": "subscribe", "v": instrument_tokens}
        await self.send(msg)
        print(f"📡 Subscribed to {instrument_tokens}")

    async def set_mode(self, mode: str, instrument_tokens: list[int]):
        msg = {"a": "mode", "v": [mode, instrument_tokens]}
        await self.send(msg)
        print(f"⚙️ Set mode '{mode}' for {instrument_tokens}")

    async def receive(self):
        while True:
            msg = await self.ws.recv()
            if isinstance(msg, (bytes, bytearray)):
                self.handle_binary(msg)
            else:
                self.handle_text(msg)

    def handle_text(self, msg: str):
        try:
            data = json.loads(msg)
            print(f"🧾 Text message:\n{json.dumps(data, indent=2)}")
        except json.JSONDecodeError:
            print("💓 Heartbeat received")

    def handle_binary(self, msg: bytes):
        if len(msg) < 2:
            print("💓 Heartbeat received")
            return

        num_packets = struct.unpack("!H", msg[0:2])[0]
        offset = 2
        for _ in range(num_packets):
            packet_len = struct.unpack("!H", msg[offset:offset + 2])[0]
            offset += 2
            packet = msg[offset:offset + packet_len]
            offset += packet_len
            data = self.parse_packet(packet)
            self.print_tick(data)

    def parse_packet(self, packet: bytes):
        token = struct.unpack("!i", packet[0:4])[0]
        length = len(packet)
        if length == 44:
            # quote mode for indices
            fields = struct.unpack("!11i", packet[:44])
            return {
                "token": fields[0],
                "ltp": fields[1] / 100,
                "open": fields[7] / 100,
                "high": fields[8] / 100,
                "low": fields[9] / 100,
                "close": fields[10] / 100,
            }
        return {"token": token, "raw_length": length}

    def print_tick(self, data: dict):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📈 NIFTY50 TICK → "
              f"LTP: {data.get('ltp')} | O: {data.get('open')} | H: {data.get('high')} | "
              f"L: {data.get('low')} | C: {data.get('close')}")


async def main():
    api_key = "gouftxcthlwelj97"
    access_token = "RC6pOWoJMoDDbiu37JZjt7E3b43gii6u"

    kite = KiteWebSocketClient(api_key, access_token)
    await kite.connect()

    await asyncio.sleep(3)

    nifty_token = 256265
    await kite.subscribe([nifty_token])
    await kite.set_mode("quote", [nifty_token])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
