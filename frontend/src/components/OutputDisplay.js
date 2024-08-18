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
