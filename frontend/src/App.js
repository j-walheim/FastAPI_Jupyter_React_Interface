import React, { useState, useEffect, useRef } from 'react';
import CodeEditor from './components/CodeEditor';
import OutputDisplay from './components/OutputDisplay';

function App() {
  const [instructions, setInstructions] = useState('create a survival plot for IO vs. Chemo and save it as survival.png');
  const [output, setOutput] = useState('');
  const [generatedCode, setGeneratedCode] = useState('');
  const ws = useRef(null);

  useEffect(() => {
    ws.current = new WebSocket('ws://localhost:8000/ws');
    ws.current.onopen = () => console.log('WebSocket Connected');
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'result') {
        setOutput(data.output);
        setGeneratedCode(data.generated_code);
      } 
      // else if (data.type === 'plotly') 

      // }
    };
    return () => {
      ws.current.close();
    };
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'execute', instructions: instructions }));
    }
  };

  return (
    <div className="App">
      <h1>FastAPI Jupyter React Interface</h1>
      <form onSubmit={handleSubmit}>
        <CodeEditor
          code={instructions}
          setCode={setInstructions}
          placeholder="Enter instructions here"
        />
        <button type="submit">Generate and Execute Code</button>
      </form>
      <div>
        <h2>Generated Code:</h2>
        <pre>{generatedCode}</pre>
      </div>
      <OutputDisplay output={output} />
    </div>
  );
}

export default App;
