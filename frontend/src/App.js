import React, { useState, useEffect, useCallback } from 'react';
import CodeEditor from './components/CodeEditor';
import OutputDisplay from './components/OutputDisplay';
import { executeCode } from './api';

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
      console.log('Received message from server:', event.data);
      const data = JSON.parse(event.data);
      if (data.output === "EXECUTION_COMPLETE") {
        setIsExecuting(false);
      } else {
        setOutput(prevOutput => prevOutput + data.output);
      }
    };
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };
    ws.onclose = () => {
      console.log('WebSocket connection closed');
      setIsConnected(false);
      setTimeout(connectWebSocket, 1000); // Attempt to reconnect after 1 second
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

  const handleCodeExecution = async () => {
    if (!isConnected) {
      alert('WebSocket is not connected. Please wait and try again.');
      return;
    }
    setOutput('');
    setIsExecuting(true);
    try {
      console.log('Executing code:', code);
      await executeCode(code);
    } catch (error) {
      console.error('Error executing code:', error);
      setOutput(`Error: ${error.message}`);
      setIsExecuting(false);
    }
  };

  return (
    <div className="App">
      <h1>Python Code Executor</h1>
      <div>WebSocket Status: {isConnected ? 'Connected' : 'Disconnected'}</div>
      <CodeEditor code={code} setCode={setCode} />
      <button onClick={handleCodeExecution} disabled={!isConnected || isExecuting}>
        {isExecuting ? 'Executing...' : 'Execute Code'}
      </button>
      <OutputDisplay output={output} />
    </div>
  );
}

export default App;
