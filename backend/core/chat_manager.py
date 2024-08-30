import asyncio
import uuid
import json
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from utils.helpers import print_verbose
from handlers.coding_agent import CodingAgent
from handlers.execution_agent import ExecutionAgent
from database.operations import ConversationMemory
from langfuse.decorators import observe, langfuse_context

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
        pattern = rf"```{block_type}\n(.*?)```"
        blocks = re.findall(pattern, content, re.DOTALL)
        return '\n'.join(block.strip() for block in blocks)

    @observe()
    async def chat(self, instructions: str, history: list, conversation_id: str, user_id: str, session):
        print_verbose(f"Starting agent conversation for instructions: {instructions}")
        
        execution_id = str(uuid.uuid4())

        message_counter = len(history) + 1

        user_message = {
            'type': 'chat_message',
            'message': {
                'role': 'human',
                'content': instructions,
            }
        }
        ConversationMemory.add_message(session, user_id, conversation_id, message_counter, user_message)
        message_counter += 1

        # ToDo: figure out right history content - we should not use the whole history, but summarise it in some way
        if isinstance(history, list):
            context = "\n".join([f"[{h[1]['message']['role']}]: {h[1]['message']['content']}" for h in history])
        else:
            print_verbose("Warning: history is not in the expected format. Treating as empty.")
            context = ""

        if len(history) < 1:
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
                    'content': f"Generated Code:\n\n```python\n{generated_code}\n```"
                }
            }
            ConversationMemory.add_message(session, user_id, conversation_id, message_counter, generated_code_message)
            message_counter += 1
            
            await self.send(generated_code_message)

            shell_commands = self.extract_code_blocks(generated_code, 'shell')
            python_code = self.extract_code_blocks(generated_code, 'python')

            if shell_commands:
                shell_result = await self.execution_agent.execute_shell_commands(shell_commands)
                shell_result_message = {
                    'type': 'chat_message',
                    'message': {
                        'role': 'system',
                        'content': f"Shell Execution Result:\n\n```\n{shell_result}\n```"
                    }
                }
                ConversationMemory.add_message(session, user_id, conversation_id, message_counter, shell_result_message)
                message_counter += 1
                await self.send(shell_result_message)

            if python_code:
                python_success, python_result = await self.execution_agent.execute_python_code(python_code)
                python_result_message = {
                    'type': 'chat_message',
                    'message': {
                        'role': 'system',
                        'content': f"Python Execution Result:\n\n```\n{python_result}\n```"
                    }
                }
                ConversationMemory.add_message(session, user_id, conversation_id, message_counter, python_result_message)
                message_counter += 1
                
                await self.send(python_result_message)

                if python_success:
                    summary = await self.generate_execution_summary(instructions, python_result)
                    summary_message = {
                        'type': 'chat_message',
                        'message': {
                            'role': 'system',
                            'content': f"Execution Summary:\n\n{summary}"
                        }
                    }
                    ConversationMemory.add_message(session, user_id, conversation_id, message_counter, summary_message)
                    message_counter += 1
                    await self.send(summary_message)
                else:
                    if attempt < self.execution_agent.max_attempts - 1:
                        print_verbose(f"Execution failed. Retrying with updated instructions.")
                        instructions = f"{instructions}\n\nExecution failed. Error: {python_result}\nPlease correct the code and try again."
                        continue
                    else:
                        print_verbose(f"Execution failed. Reached final iteration.")

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
