import asyncio
import logging
import traceback
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            data = await websocket.receive_json()
            if data['type'] == 'execute':
                code = data['code']
                execution_id = str(uuid.uuid4())
                logger.info(f"Executing code: {code}")
                
                kernel.execute(code)
                
                output = []
                while True:
                    try:
                        msg = kernel.get_iopub_msg(timeout=0.1)
                        if msg['msg_type'] == 'stream':
                            output.append(msg['content']['text'])
                        elif msg['msg_type'] in ['execute_result', 'display_data']:
                            output.append(str(msg['content']['data'].get('text/plain', '')))
                        elif msg['msg_type'] == 'status' and msg['content']['execution_state'] == 'idle':
                            break
                    except:
                        pass
                
                result = ''.join(output).strip()
                logger.info(f"Execution result: {result}")
                await websocket.send_json({
                    'type': 'result',
                    'execution_id': execution_id,
                    'output': result
                })
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket: {str(e)}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
