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
        <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
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
