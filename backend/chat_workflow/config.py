from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import colorama
from colorama import Fore, Style

load_dotenv()
global verbose
verbose = os.environ.get('VERBOSE', 'false').lower() == 'true'

def setup_app(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    colorama.init(autoreset=True)
