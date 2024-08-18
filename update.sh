#!/bin/bash

# Create necessary directories
mkdir -p frontend/src/components

# Update App.js
cat > frontend/src/App.js << EOL
import React, { useState, useEffect, useCallback } from 'react';
import CodeEditor from './components/CodeEditor';
import OutputDisplay from './components/OutputDisplay';
import './App.css';

function App() {
  const [code, setCode] = useState('');
  const [output, setOutput] = useState('');
  const [websocket, setWebsocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  const connectWebSocket = useCallback(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    ws.onopen = () => {
      console.log('WebSocket connection established');
      setIsConnected(true);
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'result') {
        console.log('Received execution result:', data.output);
        setOutput(data.output);
        setIsExecuting(false);
      }
    };
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };
    ws.onclose = () => {
      console.log('WebSocket connection closed');
      setIsConnected(false);
      setTimeout(connectWebSocket, 1000);
    };
    setWebsocket(ws);
  }, []);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (websocket) {
        websocket.close();
      }
    };
  }, [connectWebSocket]);

  const handleCodeExecution = () => {
    if (!isConnected) {
      alert('WebSocket is not connected. Please wait and try again.');
      return;
    }
    setOutput('');
    setIsExecuting(true);
    websocket.send(JSON.stringify({ type: 'execute', code }));
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleCodeExecution();
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Python Code Executor</h1>
        <div className={\`connection-status \${isConnected ? 'connected' : 'disconnected'}\`}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>
      </header>
      <main className="App-main">
        <CodeEditor 
          code={code} 
          setCode={setCode} 
          onKeyDown={handleKeyDown}
        />
        <button 
          className="execute-button" 
          onClick={handleCodeExecution} 
          disabled={!isConnected || isExecuting}
        >
          {isExecuting ? 'Executing...' : 'Execute Code'}
        </button>
        <OutputDisplay output={output} />
      </main>
    </div>
  );
}

export default App;
EOL

# Create App.css
cat > frontend/src/App.css << EOL
.App {
  font-family: Arial, sans-serif;
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.App-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.App-header h1 {
  margin: 0;
  color: #333;
}

.connection-status {
  padding: 5px 10px;
  border-radius: 5px;
  font-size: 14px;
}

.connected {
  background-color: #4CAF50;
  color: white;
}

.disconnected {
  background-color: #f44336;
  color: white;
}

.App-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.execute-button {
  padding: 10px 20px;
  font-size: 16px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.execute-button:hover:not(:disabled) {
  background-color: #45a049;
}

.execute-button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}
EOL

# Update CodeEditor.js
cat > frontend/src/components/CodeEditor.js << EOL
import React from 'react';
import './CodeEditor.css';

function CodeEditor({ code, setCode, onKeyDown }) {
  return (
    <div className="code-editor">
      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        onKeyDown={onKeyDown}
        rows={10}
        placeholder="Enter your Python code here..."
      />
    </div>
  );
}

export default CodeEditor;
EOL

# Create CodeEditor.css
cat > frontend/src/components/CodeEditor.css << EOL
.code-editor textarea {
  width: 100%;
  padding: 10px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 14px;
  border: 1px solid #ccc;
  border-radius: 5px;
  resize: vertical;
}
EOL

# Update OutputDisplay.js
cat > frontend/src/components/OutputDisplay.js << EOL
import React from 'react';
import './OutputDisplay.css';

function OutputDisplay({ output }) {
  return (
    <div className="output-display">
      <h2>Output:</h2>
      <pre>{output || 'No output yet'}</pre>
    </div>
  );
}

export default OutputDisplay;
EOL

# Create OutputDisplay.css
cat > frontend/src/components/OutputDisplay.css << EOL
.output-display {
  background-color: #f8f8f8;
  border: 1px solid #ddd;
  border-radius: 5px;
  padding: 10px;
}

.output-display h2 {
  margin-top: 0;
  color: #333;
}

.output-display pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Courier New', Courier, monospace;
  font-size: 14px;
}
EOL

echo "Frontend files have been updated successfully!"
