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
import sqlite3
from datetime import datetime
import uuid
import colorama
from colorama import Fore, Style

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

verbose = os.environ.get('VERBOSE', 'false').lower() == 'true'

# Initialize colorama
colorama.init(autoreset=True)

def print_verbose(message):
    if verbose:
        print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")

# Create a virtual environment
venv_path = Path("venv").absolute()
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
        print_verbose(f"CodingAgent: Generating code for instructions: {instructions}")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Python coding assistant. Generate executable Python code based on the given instructions and if applicable, error messages. If additional packages need to be installed, provide shell code. Use shell``` and python``` blocks, respectively, for shell commands and python code. Only provide the code blocks, no other text."),
            ("human", "{instructions}")
        ])

        response = self.llm.invoke(prompt.format_messages(instructions=instructions))
        if verbose:
            print_verbose(f"CodingAgent: Generated code:\n{response.content}")
        return response.content

    def extract_code_blocks(self, content, block_type):
        import re
        pattern = rf"```{block_type}(.*?)```"
        blocks = re.findall(pattern, content, re.DOTALL)
        return '\n'.join(block.strip() for block in blocks)

class ExecutionAgent:
    def __init__(self):
        self.max_attempts = 5
        self.coding_agent_dir = Path("coding_agent").absolute()
        self.coding_agent_dir.mkdir(exist_ok=True)

    @observe()
    def execute_code(self, generated_content):
        print_verbose(f"ExecutionAgent: Executing generated code")
        
        shell_commands = coding_agent.extract_code_blocks(generated_content, 'shell')
        python_code = coding_agent.extract_code_blocks(generated_content, 'python')

        # Execute shell commands (package installation)
        for cmd in shell_commands.split('\n'):
            if cmd.startswith('pip install'):
                packages = cmd.split('pip install ')[1].split()
                install_result = install_packages(packages)
                if "Successfully installed" not in install_result:
                    return False, f"Package installation failed: {install_result}"

        # Save Python code to a file
        script_file = self.coding_agent_dir / f"script_{uuid.uuid4()}.py"
        script_file.write_text(python_code)

        # Execute Python code from the file
        result = run_in_venv(str(script_file), self.coding_agent_dir, venv_path)
        success = result.returncode == 0
        
        print_verbose(f"ExecutionAgent: Execution result: {'Success' if success else 'Failure'}")
        print_verbose(f"ExecutionAgent: Output: {result.stdout if success else result.stderr}")
        
        return success, result.stdout if success else f"Execution failed. Error: {result.stderr}"

# Initialize the agents
coding_agent = CodingAgent()
execution_agent = ExecutionAgent()

class ConversationMemory:
    def __init__(self, db_path='conversations.db'):
        self.conn = sqlite3.connect(db_path)
        self.create_table()
        self.create_summary_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                user_id TEXT,
                message_number INTEGER,
                timestamp DATETIME,
                agent_name TEXT,
                role TEXT,
                content TEXT
            )
        ''')
        self.conn.commit()

    def create_summary_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                conversation_id TEXT PRIMARY KEY,
                user_id TEXT,
                summary TEXT
            )
        ''')
        self.conn.commit()

    def add_message(self, conversation_id, user_id, agent_name, role, content):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT MAX(message_number) FROM conversation_messages
            WHERE conversation_id = ? AND user_id = ?
        ''', (conversation_id, user_id))
        last_message_number = cursor.fetchone()[0] or 0
        new_message_number = last_message_number + 1

        cursor.execute('''
            INSERT INTO conversation_messages (conversation_id, user_id, message_number, timestamp, agent_name, role, content)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (conversation_id, user_id, new_message_number, datetime.now(), agent_name, role, content))
        self.conn.commit()

    def add_summary(self, conversation_id, user_id, summary):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO conversation_summaries (conversation_id, user_id, summary)
            VALUES (?, ?, ?)
        ''', (conversation_id, user_id, summary))
        self.conn.commit()

    def get_conversation_history(self, conversation_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT message_number, agent_name, role, content
            FROM conversation_messages
            WHERE conversation_id = ? AND user_id = ?
            ORDER BY message_number
        ''', (conversation_id, user_id))
        return cursor.fetchall()

    def get_conversation_summary(self, conversation_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT content
            FROM conversation_messages
            WHERE conversation_id = ? AND user_id = ?
            ORDER BY message_number DESC
            LIMIT 1
        ''', (conversation_id, user_id))
        last_message = cursor.fetchone()
        return last_message[0] if last_message else "No messages in this conversation."

    def get_summary(self, conversation_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT summary FROM conversation_summaries
            WHERE conversation_id = ?
        ''', (conversation_id,))
        result = cursor.fetchone()
        return result[0] if result else None

    def get_all_conversations(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT c.conversation_id, COALESCE(s.summary, 'No summary available') as summary
            FROM (SELECT DISTINCT conversation_id FROM conversation_messages WHERE user_id = ?) c
            LEFT JOIN conversation_summaries s ON c.conversation_id = s.conversation_id
        ''', (user_id,))
        conversations = [{'id': row[0], 'summary': row[1]} for row in cursor.fetchall()]
        return conversations

# Initialize the conversation memory
conversation_memory = ConversationMemory()

@observe(as_type="generation")
def generate_summary(instructions):
    llm = ChatGroq(
        model='llama-3.1-70b-versatile',
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a summarization assistant. Generate a one-sentence summary of the given conversation instructions."),
        ("human", "{instructions}")
    ])
    response = llm.invoke(prompt.format_messages(instructions=instructions))
    return response.content

@observe()
async def agent_conversation(instructions, websocket, conversation_id, user_id):
    print_verbose(f"Starting agent conversation for instructions: {instructions}")
    
    execution_id = str(uuid.uuid4())
    logger.info(f"Starting agent conversation for instructions: {instructions}")

    # Add user message to conversation memory
    conversation_memory.add_message(conversation_id, user_id, "User", "human", instructions)

    # Retrieve conversation history
    history = conversation_memory.get_conversation_history(conversation_id, user_id)
    context = "\n".join([f"[{h[0]}] {h[1]} ({h[2]}): {h[3]}" for h in history])
    
    if context:
        instructions = f"Conversation history:\n{context}\n\nNew instructions: {instructions}"

    for attempt in range(execution_agent.max_attempts):
        print_verbose(f"Attempt {attempt + 1}/{execution_agent.max_attempts}")
        
        # Coding agent generates code
        generated_code = coding_agent.generate_code(instructions)
        
        # Add coding agent message to conversation memory
        conversation_memory.add_message(conversation_id, user_id, "CodingAgent", "assistant", generated_code)
        
        # Send generated code to frontend - intermediate result not used for now
        await websocket.send_json({
            'type': 'code_generated',
            'execution_id': execution_id,
            'generated_code': generated_code
        })

        # Execution agent executes the code
        success, execution_result = execution_agent.execute_code(generated_code)
        
        # Add execution agent message to conversation memory
        conversation_memory.add_message(conversation_id, user_id, "ExecutionAgent", "system", execution_result)
        
        # Send execution result to frontend - intermediate result not used for now
        await websocket.send_json({
            'type': 'execution_result',
            'execution_id': execution_id,
            'success': success,
            'output': execution_result
        })

        if success:
            if verbose:
                print("Execution successful")
            break
        else:
            if verbose:
                if attempt < execution_agent.max_attempts - 1:
                    print(f"Execution failed. Retrying with updated instructions.")
                else:
                    print(f"Execution failed. Reached final iteration.")
                    
            instructions = f"{instructions}\n\nExecution failed. Error: {execution_result}\nPlease correct the code and try again."

    # Send final results
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

    # Generate and store summary after the first message
    if len(history) == 0:
        summary = generate_summary(instructions)
        conversation_memory.add_summary(conversation_id, user_id, summary)

    return generated_code, execution_result

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    conversation_id = str(uuid.uuid4())
    user_id = "test_user"
    
    await websocket.send_json({
        'type': 'conversation_id',
        'conversation_id': conversation_id
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            if data['type'] == 'execute':
                instructions = data['instructions']
                conversation_id = data.get('conversation_id', conversation_id)
                await agent_conversation(instructions, websocket, conversation_id, user_id)
            elif data['type'] == 'load_conversation':
                conversation_id = data['conversation_id']
                history = conversation_memory.get_conversation_history(conversation_id, user_id)
                await websocket.send_json({
                    'type': 'conversation_summary',
                    'conversation_id': conversation_id,
                    'summary': history[-1] if history else "No messages in this conversation."
                })
            elif data['type'] == 'get_conversations':
                conversations = conversation_memory.get_all_conversations(user_id)
                await websocket.send_json({
                    'type': 'all_conversations',
                    'conversations': conversations
                })
            elif data['type'] == 'new_conversation':
                conversation_id = data['conversation_id']
                await websocket.send_json({
                    'type': 'conversation_id',
                    'conversation_id': conversation_id
                })
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket: {str(e)}")
        logger.error(traceback.format_exc())

# Ensure these functions are defined
def run_in_venv(script_path, working_dir, venv_path):
    venv_python = venv_path / 'bin' / 'python'
    current_dir = os.getcwd()
    try:
        os.chdir(working_dir)
        result = subprocess.run([str(venv_python), script_path], capture_output=True, text=True)
    finally:
        os.chdir(current_dir)
    return result

def install_packages(packages):
    if isinstance(packages, str):
        packages = [packages]
    results = []
    for package in packages:
        venv_pip = venv_path / 'bin' / 'pip'
        result = subprocess.run(f"{venv_pip} install {package}", capture_output=True, text=True, shell=True)
        results.append(f"Installation result for {package}: {result.stdout}\n{result.stderr}")
    return "\n".join(results)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
