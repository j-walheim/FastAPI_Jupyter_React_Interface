import React, { useState } from 'react';

function ChatMessage({ message, isLastMessage }) {
  const [isExpanded, setIsExpanded] = useState(!message.collapsible || isLastMessage);

  const toggleExpand = () => {
    if (message.collapsible) {
      setIsExpanded(!isExpanded);
    }
  };

  return (
    <div className={`chat-message ${message.role}`}>
      <div className="message-header" onClick={toggleExpand}>
        <span>{message.role === 'human' ? 'User' : message.role === 'assistant' ? 'AI' : 'System'}</span>
        {message.collapsible && (
          <button>{isExpanded ? 'Collapse' : 'Expand'}</button>
        )}
      </div>
      <div className="message-content">
        {message.content}
        {message.collapsible && isExpanded && message.details && (
          <pre className="message-details">{message.details}</pre>
        )}
      </div>
    </div>
  );
}

export default ChatMessage;