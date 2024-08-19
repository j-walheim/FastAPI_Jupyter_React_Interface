import React, { useState, useEffect, useRef } from 'react';
import PlotlyComponent from './components/PlotlyComponent';

function App() {
  const [inputCode, setInputCode] = useState('');
  const [output, setOutput] = useState('');
  const [plotData, setPlotData] = useState(null);
  const ws = useRef(null);

  useEffect(() => {
    ws.current = new WebSocket('ws://localhost:8000/ws');
    ws.current.onopen = () => console.log('WebSocket Connected');
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'result') {
        setOutput(data.output);
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
      ws.current.send(JSON.stringify({ type: 'execute', code: inputCode }));
    }
  };

  return (
    <div className="App">
      <h1>FastAPI Jupyter React Interface</h1>
      <form onSubmit={handleSubmit}>
        <textarea
          value={inputCode}
          onChange={(e) => setInputCode(e.target.value)}
          placeholder="Enter Python code here"
        />
        <button type="submit">Execute</button>
      </form>
      <div>
        <h2>Output:</h2>
        <pre>{output}</pre>
      </div>
      <div>
        <h2>Plot:</h2>
        {plotData && <PlotlyComponent plotData={plotData} />}
      </div>
    </div>
  );
}

export default App;
