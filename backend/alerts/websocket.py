"""
CampusShield AI — WebSocket Connection Manager
================================================
Manages WebSocket connections for real-time alert streaming.
"""

import json
import logging
import asyncio
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from jose import JWTError

from backend.auth.provider import get_auth_provider
from backend.database.connection import SessionLocal

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections.
    Supports authenticated connections and broadcast.
    """

    def __init__(self):
        # Socket ownership is held server-side from the verified token.  A
        # tenant id is never accepted from a client message or query field.
        self.active_connections: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, token: Optional[str] = None) -> bool:
        """
        Accept a WebSocket connection, optionally validating a JWT token.

        Args:
            websocket: The WebSocket connection
            token: Optional JWT for authentication

        Returns:
            True if connection accepted, False if rejected
        """
        # Validate token if provided
        if token:
            try:
                # Use the same local-JWT/Cognito verification boundary as
                # HTTP routes; WebSockets must not become an auth bypass.
                db = SessionLocal()
                try:
                    payload = get_auth_provider().verify_token(token, db)
                finally:
                    db.close()
                username = payload.get("sub", "anonymous")
                tenant_id = payload.get("tenant_id")
                if not tenant_id:
                    raise JWTError("Token missing tenant_id claim")
                logger.info("WebSocket authenticated: %s", username)
            except (JWTError, ValueError):
                logger.warning("WebSocket connection rejected: invalid token")
                await websocket.close(code=4001)
                return False

        else:
            # Alert streams are protected: anonymous sockets must never see
            # tenant data.  This branch remains explicit for clarity.
            await websocket.close(code=4001)
            return False

        await websocket.accept()
        async with self._lock:
            self.active_connections[websocket] = tenant_id
        logger.info(
            f"WebSocket connected. Active connections: {len(self.active_connections)}"
        )
        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        async with self._lock:
            self.active_connections.pop(websocket, None)
        logger.info(
            f"WebSocket disconnected. Active connections: {len(self.active_connections)}"
        )

    async def broadcast(self, message: dict, tenant_id: str) -> None:
        """
        Send a message to all connected WebSocket clients.
        Automatically cleans up dead connections.
        """
        dead_connections = []
        async with self._lock:
            connections = [
                socket for socket, socket_tenant in self.active_connections.items()
                if socket_tenant == tenant_id
            ]

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for dc in dead_connections:
                    self.active_connections.pop(dc, None)
            logger.info(f"Cleaned up {len(dead_connections)} dead WebSocket connections")

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        """Send a message to a specific WebSocket client."""
        try:
            await websocket.send_json(message)
        except Exception:
            await self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


# Module-level singleton
manager = ConnectionManager()


async def broadcast_alert(alert_data: dict) -> None:
    """Broadcast an alert only to sockets in its authenticated tenant."""
    tenant_id = alert_data.get("tenant_id")
    if tenant_id:
        await manager.broadcast(alert_data, tenant_id=tenant_id)


async def broadcast_progress(progress_data: dict, tenant_id: str) -> None:
    """Broadcast processing progress only to the originating tenant."""
    await manager.broadcast({
        "type": "progress",
        **progress_data,
    }, tenant_id=tenant_id)
