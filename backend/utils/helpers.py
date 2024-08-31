import subprocess
import venv
from pathlib import Path
import os
from colorama import Fore, Style
from chat_workflow.config import verbose

# Create a virtual environment
venv_path = Path("venv").absolute()
venv.create(venv_path, with_pip=True)

def print_verbose(message):
    if verbose:
        print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")

def install_packages(packages):
    print_verbose(f"Installing packages: {packages}")
    venv_path = Path("venv").absolute()
    result = subprocess.run([f"{venv_path}/bin/pip", "install"] + packages, capture_output=True, text=True)
    return f"Installation {'succeeded' if result.returncode == 0 else 'failed'}: {result.stdout or result.stderr}"

def run_in_venv(script_path, working_dir):
    print_verbose(f"Running script: {script_path}")
    python_executable = f"{venv_path}/bin/python"
    result = subprocess.run([python_executable, script_path], cwd=working_dir, capture_output=True, text=True)
    return result


