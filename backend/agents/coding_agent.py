from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from utils.helpers import print_verbose
from langfuse.decorators import observe

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
            ("system", "You are a Python coding assistant. Generate executable Python code based on the given instructions and if applicable, error messages. If additional packages need to be installed, provide shell code. Use shell blocks, respectively, for shell commands and python code. Only provide the code blocks, no other text."),
            ("human", "{instructions}")
        ])

        response = self.llm.invoke(prompt.format_messages(instructions=instructions))

        print_verbose(f"CodingAgent: Generated code:\n{response.content}")
        return response.content
