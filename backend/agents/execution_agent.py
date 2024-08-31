import uuid
from pathlib import Path
from utils.helpers import print_verbose, install_packages, run_in_venv
from langfuse.decorators import observe

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
        
        script_file = self.coding_agent_dir / f"script_{uuid.uuid4()}.py"
        script_file.write_text(python_code)

        result = run_in_venv(str(script_file), self.coding_agent_dir)
        success = result.returncode == 0
        
        print_verbose(f"ExecutionAgent: Execution result: {'Success' if success else 'Failure'}")
        print_verbose(f"ExecutionAgent: Output: {result.stdout if success else result.stderr}")
        
        return success, result.stdout if success else f"Execution failed. Error: {result.stderr}"
