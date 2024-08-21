import React, { useState, useEffect, useRef } from 'react';
import PlotlyComponent from './components/PlotlyComponent';
import CodeEditor from './components/CodeEditor';
import OutputDisplay from './components/OutputDisplay';

function App() {
  const [instructions, setInstructions] = useState('create a survival plot for IO vs. Chemo and save it as survival.png');
  const [output, setOutput] = useState('');
  const [generatedCode, setGeneratedCode] = useState('');
  const [plotData, setPlotData] = useState(null);
  const ws = useRef(null);

  useEffect(() => {
    ws.current = new WebSocket('ws://localhost:8000/ws');
    ws.current.onopen = () => console.log('WebSocket Connected');
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'result') {
        setOutput(data.output);
        setGeneratedCode(data.generated_code);
      } else if (data.type === 'plotly') {
        setPlotData(data.plot_data);
      }
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
      <div>
        <h2>Plot:</h2>
        {plotData && <PlotlyComponent plotData={plotData} />}
      </div>
    </div>
  );
}

export default App;
