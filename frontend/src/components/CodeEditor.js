import React from 'react';
import './CodeEditor.css';

function CodeEditor({ code, setCode, onKeyDown, placeholder }) {
  return (
    <div className="code-editor">
      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        onKeyDown={onKeyDown}
        rows={10}
        placeholder={placeholder || "Enter your code here..."}
      />
    </div>
  );
}

export default CodeEditor;
