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
import venv
import openai
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate

from langfuse.decorators import observe, langfuse_context

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

# Create a virtual environment
venv_path = Path("venv")
venv.create(venv_path, with_pip=True)

class CodingAgent:
    def __init__(self):
        self.llm = ChatGroq(
            model='llama-3.1-70b-versatile',
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2
        )

    @observe(as_type="generation")
    def generate_code(self, instructions):
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Python coding assistant. Generate executable Python code based on the given instructions. Provide shell code if you need to install packages. Use shell``` and python``` blocks, respectively, for shell commands and python code. Only provide the code blocks, no other text."),
            ("human", instructions)
        ])

        response = self.llm.invoke(prompt.format_messages(instructions=instructions))
        return response.content

    def extract_code_blocks(self, content, block_type):
        import re
        pattern = rf"```{block_type}(.*?)```"
        blocks = re.findall(pattern, content, re.DOTALL)
        return '\n'.join(block.strip() for block in blocks)

class ExecutionAgent:
    def __init__(self):
        self.max_attempts = 5

    @observe()
    def execute_code(self, generated_content):
        shell_commands = coding_agent.extract_code_blocks(generated_content, 'shell')
        python_code = coding_agent.extract_code_blocks(generated_content, 'python')

        # Execute shell commands (package installation)
        installation_errors = []
        for cmd in shell_commands.split('\n'):
            if cmd.startswith('pip install'):
                packages = cmd.split('pip install ')[1].split()
                install_result = install_packages(packages)
                if "Successfully installed" not in install_result:
                    installation_errors.append(f"Failed to install {' '.join(packages)}. Error: {install_result}")

        if installation_errors:
            return False, "Package installation failed:\n" + "\n".join(installation_errors)

        # Execute Python code
        result = run_in_venv(f"python -c '{python_code}'")
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, f"Execution failed. Error: {result.stderr}"

# Initialize the agents
coding_agent = CodingAgent()
execution_agent = ExecutionAgent()

@observe()
async def agent_conversation(instructions, websocket):
    execution_id = str(uuid.uuid4())
    logger.info(f"Starting agent conversation for instructions: {instructions}")

    for attempt in range(execution_agent.max_attempts):
        # Coding agent generates code
        generated_code = coding_agent.generate_code(instructions)
        
        # Send generated code to frontend
        await websocket.send_json({
            'type': 'code_generated',
            'execution_id': execution_id,
            'generated_code': generated_code
        })

        # Execution agent executes the code
        success, execution_result = execution_agent.execute_code(generated_code)
        
        # Send execution result to frontend
        await websocket.send_json({
            'type': 'execution_result',
            'execution_id': execution_id,
            'success': success,
            'output': execution_result
        })

        if success:
            break
        else:
            instructions = f"{instructions}\n\nExecution failed. Error: {execution_result}\nPlease correct the code and try again."

    # Send final results
    await websocket.send_json({
        'type': 'final_result',
        'execution_id': execution_id,
        'generated_code': generated_code,
        'output': execution_result
    })

    # Check if the output contains a Plotly figure
    if execution_result.startswith('{"data":[{"'):
        plot_data = execution_result[execution_result.index('{"data":[{"'):]
        await websocket.send_json({
            'type': 'plotly',
            'execution_id': execution_id,
            'plot_data': plot_data
        })

    return generated_code, execution_result

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
                await agent_conversation(instructions, websocket)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket: {str(e)}")
        logger.error(traceback.format_exc())

# Ensure these functions are defined
def run_in_venv(cmd):
    venv_python = os.path.join(venv_path, 'bin', 'python')
    return subprocess.run(f"{venv_python} -c '{cmd}'", capture_output=True, text=True, shell=True)

def install_packages(packages):
    if isinstance(packages, str):
        packages = [packages]
    results = []
    for package in packages:
        venv_pip = os.path.join(venv_path, 'bin', 'pip')
        result = subprocess.run(f"{venv_pip} install {package}", capture_output=True, text=True, shell=True)
        results.append(f"Installation result for {package}: {result.stdout}\n{result.stderr}")
    return "\n".join(results)

def create_sample_plot():
    x = [1, 2, 3, 4, 5]
    y = [1, 4, 2, 3, 5]
    fig = go.Figure(data=go.Scatter(x=x, y=y, mode='lines'))
    fig.update_layout(title='Sample Line Plot')
    return pio.to_json(fig)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
