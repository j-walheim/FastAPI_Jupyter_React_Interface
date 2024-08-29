# React-FastAPI-Jupyter Integration

This project was created to experiment with linking a React frontend to a FastAPI backend for interactive, AI-driven code generation and execution.

## Features

- LLM-powered code generation based on user instructions
- Real-time code execution using Jupyter kernels
- Interactive plotting with Plotly
- WebSocket communication between frontend and backend
- Conversation memory using SQLite
- Virtual environment for package management

## Setup

### Backend
1. Navigate to the `backend` directory
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - On Windows: `venv\Scripts\activate`
   - On macOS/Linux: `source venv/bin/activate`
4. Install dependencies: `pip install fastapi uvicorn jupyter_client websockets plotly langchain_groq python-dotenv colorama`
5. Create a `.env` file and add necessary environment variables (e.g., API keys)
6. Run the FastAPI server: `python main.py`

### Frontend
1. Navigate to the `frontend` directory
2. Install dependencies: `npm install`
3. Start the React app: `npm start`

## Usage
1. Open your browser and go to `http://localhost:3000`
2. Enter instructions in the text area (e.g., "create a survival plot for IO vs. Chemo and save it as survival.png")
3. Click "Generate and Execute Code" to generate and run the code
4. View the AI-generated code and its output in real-time below the input area

## Project Structure

- `backend/`: FastAPI server and LLM-based code generation logic
- `frontend/`: React application for user interface
- `coding_agent/`: Directory for storing generated Python scripts
- `conversations.db`: SQLite database for storing conversation history

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.