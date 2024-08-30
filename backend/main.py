from fastapi import FastAPI
from core.config import setup_app
from core.websocket_handler import websocket_endpoint
from database.operations import create_db_and_tables

app = FastAPI()

setup_app(app)

app.add_api_websocket_route("/ws", websocket_endpoint)

if __name__ == "__main__":
    create_db_and_tables()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
