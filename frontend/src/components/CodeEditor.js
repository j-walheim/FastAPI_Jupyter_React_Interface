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
