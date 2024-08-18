import asyncio
import logging
import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ksm = KernelSpecManager()
kernel_specs = ksm.find_kernel_specs()
if not kernel_specs:
    raise RuntimeError("No Jupyter kernels found. Please install at least one kernel.")

kernel_name = next(iter(kernel_specs))
logger.info(f"Using kernel: {kernel_name}")

km = KernelManager(kernel_name=kernel_name)
km.start_kernel()
kernel = km.client()
kernel.start_channels()

class CodeExecution(BaseModel):
    code: str

@app.post("/execute")
async def execute_code(code_execution: CodeExecution):
    logger.info(f"Executing code: {code_execution.code}")
    msg_id = kernel.execute(code_execution.code)
    return {"message": "Code execution started", "msg_id": msg_id}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            try:
                msg = kernel.get_iopub_msg(timeout=1)
                logger.info(f"Received message from kernel: {msg['msg_type']}")
                
                if msg['msg_type'] == 'stream':
                    output = msg['content']['text']
                elif msg['msg_type'] in ['execute_result', 'display_data']:
                    output = str(msg['content']['data'].get('text/plain', ''))
                elif msg['msg_type'] == 'status' and msg['content']['execution_state'] == 'idle':
                    output = "EXECUTION_COMPLETE"
                else:
                    continue  # Skip other message types
                
                logger.info(f"Sending output to frontend: {output}")
                await websocket.send_json({"output": output})
            except asyncio.TimeoutError:
                pass  # This is expected behavior, just continue
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        logger.info("Closing WebSocket connection")

@app.get("/kernels")
async def list_kernels():
    return {"kernels": list(ksm.find_kernel_specs().keys())}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
