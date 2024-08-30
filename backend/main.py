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
from dotenv import load_dotenv
import subprocess
import venv
import openai
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
import sqlite3
from datetime import datetime
import colorama
from colorama import Fore, Style
from langfuse.decorators import observe, langfuse_context
from typing import List, Tuple, Dict, Any, Optional
import json

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

class ExecutionAgent:
    def __init__(self):
        self.max_attempts = 5
        self.coding_agent_dir = Path("coding_agent").absolute()
        self.coding_agent_dir.mkdir(exist_ok=True)

    @observe()
    async def execute_shell_commands(self, shell_commands: str):
        print_verbose(f"ExecutionAgent: Executing shell commands")
        
        results = []
        for cmd in shell_commands.split('\n'):
            if cmd.startswith('pip install'):
                packages = cmd.split('pip install ')[1].split()
                install_result = install_packages(packages)
                results.append(install_result)
        
        return "\n".join(results)

    @observe()
    async def execute_python_code(self, python_code: str):
        print_verbose(f"ExecutionAgent: Executing Python code")
        
        # Save Python code to a file
        script_file = self.coding_agent_dir / f"script_{uuid.uuid4()}.py"
        script_file.write_text(python_code)

        # Execute Python code from the file
        result = run_in_venv(str(script_file), self.coding_agent_dir, venv_path)
        success = result.returncode == 0
        
        print_verbose(f"ExecutionAgent: Execution result: {'Success' if success else 'Failure'}")
        print_verbose(f"ExecutionAgent: Output: {result.stdout if success else result.stderr}")
        
        return success, result.stdout if success else f"Execution failed. Error: {result.stderr}"

class ChatManager:
    def __init__(self, message_queue: asyncio.Queue):
        self.message_queue = message_queue
        self.coding_agent = CodingAgent()
        self.execution_agent = ExecutionAgent()
        self.llm = ChatGroq(
            model='llama-3.1-70b-versatile',
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2
        )

    async def send(self, message: dict):
        await self.message_queue.put(message)

    def extract_code_blocks(self, content, block_type):
        import re
        pattern = rf"```{block_type}(.*?)```"
        blocks = re.findall(pattern, content, re.DOTALL)
        return '\n'.join(block.strip() for block in blocks)

    @observe()
    async def chat(self, instructions: str, history: List[Dict[str, Any]], conversation_id: str, user_id: str):
        print_verbose(f"Starting agent conversation for instructions: {instructions}")
        
        execution_id = str(uuid.uuid4())
        logger.info(f"Starting agent conversation for instructions: {instructions}")

        # Add user message to conversation memory
        user_message = {
            'type': 'chat_message',
            'message': {
                'role': 'human',
                'content': instructions,
            }
        }
        conversation_memory.add_message(conversation_id, user_id, user_message)

        context = "\n".join([f"[{h[0]}] {h[1]} ({h[2]}): {h[3]}" for h in history])
        
        if len(history) == 1:
            summary = self.generate_summary(instructions)
            conversation_memory.add_summary(conversation_id, user_id, summary)
            print_verbose(f"Generated and stored summary: {summary}")
        
        if context:
            instructions = f"Conversation history:\n{context}\n\nNew instructions: {instructions}"

        python_result = "No Python code was executed."
        generated_code = ""

        for attempt in range(self.execution_agent.max_attempts):
            print_verbose(f"Attempt {attempt + 1}/{self.execution_agent.max_attempts}")
            
            generated_code = self.coding_agent.generate_code(instructions)
            generated_code_message = {
                'type': 'chat_message',
                'message': {
                    'role': 'assistant',
                    'content': 'Generated Code:',
                    'details': generated_code,
                    'collapsible': True
                }
            }
            conversation_memory.add_message(conversation_id, user_id, generated_code_message)
            
            await self.send(generated_code_message)

            shell_commands = self.extract_code_blocks(generated_code, 'shell')
            python_code = self.extract_code_blocks(generated_code, 'python')

            # Execute shell commands if present
            if shell_commands:
                shell_result = await self.execution_agent.execute_shell_commands(shell_commands)
                shell_result_message = {
                    'type': 'chat_message',
                    'message': {
                        'role': 'system',
                        'content': 'Shell Execution Result:',
                        'details': shell_result,
                        'collapsible': True
                    }
                }
                conversation_memory.add_message(conversation_id, user_id, shell_result_message)
                await self.send(shell_result_message)

            # Execute Python code if present
            if python_code:
                python_success, python_result = await self.execution_agent.execute_python_code(python_code)
                python_result_message = {
                    'type': 'chat_message',
                    'message': {
                        'role': 'system',
                        'content': 'Python Execution Result:',
                        'details': python_result,
                        'collapsible': True
                    }
                }
                conversation_memory.add_message(conversation_id, user_id, python_result_message)
                
                await self.send(python_result_message)

                if python_success:
                    # Generate and send summary after successful execution
                    summary = await self.generate_execution_summary(instructions, python_result)
                    summary_message = {
                        'type': 'chat_message',
                        'message': {
                            'role': 'system',
                            'content': 'Execution Summary:',
                            'details': summary,
                            'collapsible': True
                        }
                    }
                    conversation_memory.add_message(conversation_id, user_id, summary_message)
                    await self.send(summary_message)
                else:
                    if attempt < self.execution_agent.max_attempts - 1:
                        print_verbose(f"Execution failed. Retrying with updated instructions.")
                        instructions = f"{instructions}\n\nExecution failed. Error: {python_result}\nPlease correct the code and try again."
                        continue
                    else:
                        print_verbose(f"Execution failed. Reached final iteration.")

            # If we've reached this point, either there was no code to execute or execution was successful
            break

        await self.send({
            'type': 'result',
            'execution_id': execution_id,
            'generated_code': generated_code,
            'output': python_result
        })

        if python_result.startswith('{"data":[{"'):
            plot_data = python_result[python_result.index('{"data":[{"'):]
            await self.send({
                'type': 'plotly',
                'execution_id': execution_id,
                'plot_data': plot_data
            })

        return generated_code, python_result

    @observe(as_type="generation")
    def generate_summary(self, instructions):
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

    @observe(as_type="generation")
    async def generate_execution_summary(self, instructions: str, execution_result: str):
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI assistant that summarizes code execution results. Provide a concise summary of the given instructions and execution results."),
            ("human", "Instructions: {instructions}\n\nExecution Result: {execution_result}\n\nPlease provide a brief summary of what was requested and the outcome of the execution.")
        ])
        response = self.llm.invoke(prompt.format_messages(instructions=instructions, execution_result=execution_result))
        return response.content

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
                message_data TEXT
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

    def add_message(self, conversation_id, user_id, message_data):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT MAX(message_number) FROM conversation_messages
            WHERE conversation_id = ? AND user_id = ?
        ''', (conversation_id, user_id))
        last_message_number = cursor.fetchone()[0] or 0
        new_message_number = last_message_number + 1

        cursor.execute('''
            INSERT INTO conversation_messages (conversation_id, user_id, message_number, timestamp, message_data)
            VALUES (?, ?, ?, ?, ?)
        ''', (conversation_id, user_id, new_message_number, datetime.now(), json.dumps(message_data)))
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
            SELECT message_number, message_data
            FROM conversation_messages
            WHERE conversation_id = ? AND user_id = ?
            ORDER BY message_number
        ''', (conversation_id, user_id))
        return [(row[0], json.loads(row[1])) for row in cursor.fetchall()]

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

# Initialize managers
connection_manager = WebSocketConnectionManager()
chat_manager = ChatManager(asyncio.Queue())
conversation_memory = ConversationMemory()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = str(uuid.uuid4())
    await connection_manager.connect(websocket, client_id)
    
    conversation_id = str(uuid.uuid4())
    user_id = "test_user"
    
    await connection_manager.send_message({
        'type': 'conversation_id',
        'conversation_id': conversation_id
    }, websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            if data['type'] == 'execute':
                instructions = data['instructions']
                conversation_id = data.get('conversation_id', conversation_id)
                history = conversation_memory.get_conversation_history(conversation_id, user_id)
                await chat_manager.chat(instructions, history, conversation_id, user_id)
            elif data['type'] == 'load_conversation':
                conversation_id = data['conversation_id']
                await load_conversation(websocket, conversation_id, user_id)
            elif data['type'] == 'get_conversations':
                conversations = conversation_memory.get_all_conversations(user_id)
                await connection_manager.send_message({
                    'type': 'all_conversations',
                    'conversations': conversations
                }, websocket)
            elif data['type'] == 'new_conversation':
                conversation_id = data['conversation_id']
                await connection_manager.send_message({
                    'type': 'conversation_id',
                    'conversation_id': conversation_id
                }, websocket)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
        await connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in WebSocket: {str(e)}")
        logger.error(traceback.format_exc())
        await connection_manager.disconnect(websocket)

async def message_consumer(queue: asyncio.Queue):
    while True:
        message = await queue.get()
        await connection_manager.broadcast(message)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(message_consumer(chat_manager.message_queue))

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

async def load_conversation(websocket: WebSocket, conversation_id: str, user_id: str):
    history = conversation_memory.get_conversation_history(conversation_id, user_id)
    summary = conversation_memory.get_summary(conversation_id)
    
    # Send each message in the history
    for _, message in history:
        await connection_manager.send_message(message, websocket)
    
    # Send the summary
    await connection_manager.send_message({
        'type': 'conversation_summary',
        'summary': summary
    }, websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
