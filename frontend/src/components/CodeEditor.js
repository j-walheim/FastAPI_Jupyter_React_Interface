import React from 'react';

function CodeEditor({ code, setCode }) {
  return (
    <textarea
      value={code}
      onChange={(e) => setCode(e.target.value)}
      rows={10}
      cols={50}
      placeholder="Enter your Python code here..."
    />
  );
}

export default CodeEditor;
