"""
Compatibility shim: re-export KiteWebSocketClient from the canonical
implementation under services/data_service/extraction/live_data.py.

This keeps existing imports of `core.messaging.web_socket.KiteWebSocketClient`
working while ensuring there's a single hardened implementation in the codebase.
"""

from services.data_service.extraction.live_data import KiteWebSocketClient  # re-export

__all__ = ["KiteWebSocketClient"]
