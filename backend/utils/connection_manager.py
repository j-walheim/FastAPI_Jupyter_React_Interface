import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Tuple, Dict

class WebSocketConnectionManager:
    def __init__(self):
        self.active_connections: List[Tuple[WebSocket, str]] = []
        self.active_connections_lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        async with self.active_connections_lock:
            self.active_connections.append((websocket, client_id))
            print(f"New Connection: {client_id}, Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self.active_connections_lock:
            self.active_connections = [conn for conn in self.active_connections if conn[0] != websocket]
            print(f"Connection Closed. Total: {len(self.active_connections)}")

    async def send_message(self, message: Dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            print("Error: Tried to send a message to a closed WebSocket")
            await self.disconnect(websocket)
        except Exception as e:
            print(f"Error in sending message: {str(e)}")
            await self.disconnect(websocket)

    async def broadcast(self, message: Dict):
        for connection, _ in self.active_connections[:]:
            await self.send_message(message, connection)

connection_manager = WebSocketConnectionManager()
