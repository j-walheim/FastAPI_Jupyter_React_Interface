import React from 'react';

function OutputDisplay({ output }) {
  return (
    <div>
      <h2>Output:</h2>
      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', border: '1px solid black', padding: '10px' }}>
        {output || 'No output yet'}
      </pre>
    </div>
  );
}

export default OutputDisplay;
