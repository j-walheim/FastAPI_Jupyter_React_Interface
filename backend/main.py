import asyncio
import logging
import traceback
import uuid
import os
import sys
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
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
from datetime import datetime
import colorama
from colorama import Fore, Style
from langfuse.decorators import observe, langfuse_context
from typing import List, Tuple, Dict, Any, Optional
import json
from sqlmodel import Session, select, create_engine, SQLModel
from models import Message, Conversation

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

# Database setup
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./sql_app.db")
engine = create_engine(DATABASE_URL)

# Create tables
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# Dependency to get the database session
def get_session():
    with Session(engine) as session:
        yield session

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
    async def chat(self, instructions: str, history: List[Dict[str, Any]], conversation_id: str, user_id: str, session: Session):
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
        ConversationMemory.add_message(session, user_id, len(history) + 1, user_message)

        context = "\n".join([f"[{h['message']['role']}]: {h['message']['content']}" for h in history])
        
        if len(history) == 1:
            summary = self.generate_summary(instructions)
            ConversationMemory.update_summary(session, user_id, summary)
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
            ConversationMemory.add_message(session, user_id, len(history) + 2 + attempt * 2, generated_code_message)
            
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
                ConversationMemory.add_message(session, user_id, len(history) + 3 + attempt * 2, shell_result_message)
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
                ConversationMemory.add_message(session, user_id, len(history) + 4 + attempt * 2, python_result_message)
                
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
                    ConversationMemory.add_message(session, user_id, len(history) + 5 + attempt * 2, summary_message)
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
    @staticmethod
    def add_message(session: Session, user_id: str, message_number: int, message_data: dict):
        conversation = session.exec(select(Conversation).where(Conversation.user_id == user_id)).first()
        if not conversation:
            conversation = Conversation(user_id=user_id)
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
        
        message = Message(
            conversation_id=conversation.id,
            user_id=user_id,
            message_number=message_number,
            message_data=json.dumps(message_data)
        )
        session.add(message)
        session.commit()

    @staticmethod
    def get_conversation_history(session: Session, conversation_id: str, user_id: str):
        messages = session.exec(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.message_number)).all()
        return [(message.message_number, json.loads(message.message_data)) for message in messages]

    @staticmethod
    def update_summary(session: Session, user_id: str, summary: str):
        conversation = session.exec(select(Conversation).where(Conversation.user_id == user_id)).first()
        if conversation:
            conversation.summary = summary
            conversation.updated_at = datetime.utcnow()
            session.commit()

    @staticmethod
    def get_summary(session: Session, conversation_id: str):
        conversation = session.exec(select(Conversation).where(Conversation.id == conversation_id)).first()
        return conversation.summary if conversation else None

    @staticmethod
    def get_all_conversations(session: Session, user_id: str):
        conversations = session.exec(select(Conversation).where(Conversation.user_id == user_id)).all()
        return [{'id': conv.id, 'summary': conv.summary or 'No summary available'} for conv in conversations]

    @staticmethod
    def create_new_conversation(session: Session, user_id: str, conversation_id: str):
        conversation = Conversation(id=conversation_id, user_id=user_id)
        session.add(conversation)
        session.commit()
        return conversation

# Initialize managers
connection_manager = WebSocketConnectionManager()
chat_manager = ChatManager(asyncio.Queue())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session: Session = Depends(get_session)):
    client_id = str(uuid.uuid4())
    await connection_manager.connect(websocket, client_id)
    
    user_id = "test_user"
    
    try:
        while True:
            data = await websocket.receive_json()
            print(f"Received data: {data}")
            
            if data['type'] == 'message':
                instructions = data['message']
                conversation_id = data['conversation_id']
                history = ConversationMemory.get_conversation_history(session, conversation_id, user_id)
                
                generated_code, execution_result = await chat_manager.chat(instructions, history, conversation_id, user_id, session)
            
            elif data['type'] == 'meta':
                if data['action'] == 'get_conversations':
                    print("Fetching conversations")
                    conversations = ConversationMemory.get_all_conversations(session, user_id)
                    print(f"Found {len(conversations)} conversations")
                    await connection_manager.send_message({
                        'type': 'meta',
                        'action': 'conversations',
                        'data': conversations
                    }, websocket)
                elif data['action'] == 'load_conversation':
                    conversation_id = data['conversation_id']
                    history = ConversationMemory.get_conversation_history(session, conversation_id, user_id)
                    summary = ConversationMemory.get_summary(session, conversation_id)
                    
                    print(f"Loading conversation: {conversation_id}")
                    print(f"History length: {len(history)}")
                    
                    # Send the conversation ID and summary first
                    await connection_manager.send_message({
                        'type': 'meta',
                        'action': 'conversation_info',
                        'data': {
                            'id': conversation_id,
                            'summary': summary
                        }
                    }, websocket)
                    
                    # Send each message individually
                    for msg_number, msg_data in history:
                        try:
                            parsed_msg = msg_data
                            await connection_manager.send_message({
                                'type': 'chat_message',
                                'message': parsed_msg['message']
                            }, websocket)
                            print(f"  Sent message {msg_number}: Role: {parsed_msg['message']['role']}, Content: {parsed_msg['message']['content'][:50]}...")
                        except Exception as e:
                            print(f"  Error sending message {msg_number}: {e}")
                            print(f"  Raw message data: {msg_data}")
                    
                    # Send a message to indicate that all messages have been sent
                    await connection_manager.send_message({
                        'type': 'meta',
                        'action': 'conversation_loaded'
                    }, websocket)
                elif data['action'] == 'new_conversation':
                    new_conversation_id = str(uuid.uuid4())
                    ConversationMemory.create_new_conversation(session, user_id, new_conversation_id)
                    await connection_manager.send_message({
                        'type': 'meta',
                        'action': 'new_conversation',
                        'data': {
                            'conversation_id': new_conversation_id
                        }
                    }, websocket)

    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)

def install_packages(packages):
    print_verbose(f"Installing packages: {packages}")
    result = subprocess.run([f"{venv_path}/bin/pip", "install"] + packages, capture_output=True, text=True)
    return f"Installation {'succeeded' if result.returncode == 0 else 'failed'}: {result.stdout or result.stderr}"

def run_in_venv(script_path, working_dir, venv_path):
    print_verbose(f"Running script: {script_path}")
    python_executable = f"{venv_path}/bin/python"
    result = subprocess.run([python_executable, script_path], cwd=working_dir, capture_output=True, text=True)
    return result

if __name__ == "__main__":
    create_db_and_tables()  
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
