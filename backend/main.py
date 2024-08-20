import asyncio
import logging
import traceback
import uuid
import os
import sys
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
import plotly.graph_objects as go
import plotly.io as pio
from autogen import AssistantAgent, UserProxyAgent
from autogen.coding import LocalCommandLineCodeExecutor
from dotenv import load_dotenv
import subprocess

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

# Load environment variables
load_dotenv()

# Set up the coding agent
config_list = [
    {
        "model": "llama-3.1-70b-versatile",
        "api_key": os.environ.get("GROQ_API_KEY"),
        "api_type": "groq",
    }
]

workdir = Path("coding")
workdir.mkdir(exist_ok=True)



def install_packages(packages):
    if isinstance(packages, str):
        packages = [packages]
    for package in packages:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return f"Successfully installed: {', '.join(packages)}"


system_message = """You are a helpful AI assistant who writes code and the user executes it.
Solve tasks using your coding and language skills.
In the following cases, suggest python code (in a python coding block) for the user to execute.
Solve the task step by step if you need to. If a plan is not provided, explain your plan first. Be clear which step uses code, and which step uses your language skill.
When using code, you must indicate the script type in the code block. The user cannot provide any other feedback or perform any other action beyond executing the code you suggest. The user can't modify your code. So do not suggest incomplete code which requires users to modify. Don't use a code block if it's not intended to be executed by the user.
Don't include multiple code blocks in one response. Do not ask users to copy and paste the result. Instead, use 'print' function for the output when relevant. Check the execution result returned by the user.
If you need to install packages, use the install_packages function. For example: install_packages(["numpy", "pandas"])
If the result indicates there is an error, fix the error and output the code again. Suggest the full code instead of partial code or code changes. If the error can't be fixed or if the task is not solved even after the code is executed successfully, analyze the problem, revisit your assumption, collect additional info you need, and think of a different approach to try.
When you find an answer, verify the answer carefully. Include verifiable evidence in your response if possible."""



code_executor = LocalCommandLineCodeExecutor(work_dir=workdir)

user_proxy_agent = UserProxyAgent(
    name="User",
    code_execution_config={"executor": code_executor},
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
#    is_termination_msg=lambda msg: "FINISH" in msg.get("content"),
    function_map={"install_packages": install_packages}
)

assistant_agent = AssistantAgent(
    name="Groq Assistant",
#    system_message=system_message,
    llm_config={"config_list": config_list},
)

def create_sample_plot():
    x = [1, 2, 3, 4, 5]
    y = [1, 4, 2, 3, 5]
    fig = go.Figure(data=go.Scatter(x=x, y=y, mode='lines'))
    fig.update_layout(title='Sample Line Plot')
    return pio.to_json(fig)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    # Send the initial plot
    sample_plot = create_sample_plot()
    await websocket.send_json({
        'type': 'plotly',
        'execution_id': str(uuid.uuid4()),
        'plot_data': sample_plot
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            if data['type'] == 'execute':
                instructions = data['instructions']
                execution_id = str(uuid.uuid4())
                logger.info(f"Received instructions: {instructions}")
                
                # Use the coding agent to generate and execute code
                chat_result = user_proxy_agent.initiate_chat(
                    assistant_agent,
                    message=instructions,
                )
                
                # Extract the generated code and its output
                generated_code = chat_result.chat_history[-3]['content']  # Assuming the last message is "FINISH"
                execution_result = chat_result.chat_history[-2]['content']
                status = chat_result.chat_history[-1]['content']


                # Send the results back to the frontend
                await websocket.send_json({
                    'type': 'result',
                    'execution_id': execution_id,
                    'generated_code': generated_code,
                    'output': execution_result
                })
                
                # Check if the output contains a Plotly figure
                if 'application/vnd.plotly.v1+json' in execution_result:
                    plot_data = execution_result['application/vnd.plotly.v1+json']
                    await websocket.send_json({
                        'type': 'plotly',
                        'execution_id': execution_id,
                        'plot_data': plot_data
                    })
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket: {str(e)}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
