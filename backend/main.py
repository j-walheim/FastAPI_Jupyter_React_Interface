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

# Set up OpenAI client
client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Create a virtual environment
venv_path = Path("venv")
venv.create(venv_path, with_pip=True)

# Function to run commands in the virtual environment
def run_in_venv(cmd):
    activate_this = os.path.join(venv_path, 'bin', 'activate_this.py')
    exec(open(activate_this).read(), {'__file__': activate_this})
    return subprocess.run(cmd, capture_output=True, text=True, shell=True)

# Function to install packages in the virtual environment
def install_packages(packages):
    if isinstance(packages, str):
        packages = [packages]
    for package in packages:
        result = run_in_venv(f"pip install {package}")
    return f"Installation result: {result.stdout}\n{result.stderr}"

# Custom coding agent
class CodingAgent:
    def __init__(self):
        self.max_attempts = 5
        self.llm = ChatGroq(
            model='llama3-groq-70b-8192-tool-use-preview',
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2
        )

    async def generate_and_execute_code(self, instructions):
        for attempt in range(self.max_attempts):
            try:
                # Generate code using Groq
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are a Python coding assistant. Generate executable Python code based on the given instructions. Provide shell code if you need to install packages. Use shell``` and python``` blocks, respectively, for shell commands and python code. Only provide the code blocks, no other text."),
                    ("human", instructions)
                ])

                response = await self.llm.ainvoke(prompt.format_messages(instructions=instructions))
                generated_content = response.content

                # Extract shell and Python commands
                shell_commands = self.extract_code_blocks(generated_content, 'shell')
                python_code = self.extract_code_blocks(generated_content, 'python')

                # Execute shell commands (package installation)
                installation_errors = []
                for cmd in shell_commands.split('\n'):
                    if cmd.startswith('pip install'):
                        packages = cmd.split('pip install ')[1].split()
                        install_result = install_packages(packages)
                        if "Successfully installed" not in install_result:
                            installation_errors.append(f"Failed to install {' '.join(packages)}. Error: {install_result}")

                if installation_errors:
                    error_message = "Package installation failed:\n" + "\n".join(installation_errors)
                    continue  # Retry with the error message

                # Execute Python code
                result = run_in_venv(f"python -c '{python_code}'")
                
                if result.returncode == 0:
                    return generated_content, result.stdout  # Return the output on success
                else:
                    # If execution fails, send the error back to Groq for correction
                    error_message = f"Execution failed. Error: {result.stderr}\nPlease correct the code and try again."
                    continue
            except Exception as e:
                error_message = f"An error occurred: {str(e)}"
                continue

        # If all attempts fail, return the error message
        return generated_content, f"Failed after {self.max_attempts} attempts. {error_message} Please provide additional information or clarify your instructions."

    def extract_code_blocks(self, content, block_type):
        import re
        pattern = rf"```{block_type}(.*?)```"
        blocks = re.findall(pattern, content, re.DOTALL)
        return '\n'.join(block.strip() for block in blocks)

# Initialize the coding agent
coding_agent = CodingAgent()


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
                
                # Use the custom coding agent to generate and execute code
                generated_code, execution_result = await coding_agent.generate_and_execute_code(instructions)
                
                # Send the results back to the frontend
                await websocket.send_json({
                    'type': 'result',
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
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket: {str(e)}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
