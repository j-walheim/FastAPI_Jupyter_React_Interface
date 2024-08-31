import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import Plot from 'react-plotly.js';
import PlotlyComponent from './PlotlyComponent';

function ChatMessage({ message, isLastMessage, isUserMessage }) {
  const [isExpanded, setIsExpanded] = useState(isUserMessage || isLastMessage);

  const toggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  const getRoleName = (role) => {
    switch (role) {
      case 'human':
        return 'User';
      case 'assistant':
        return 'AI';
      case 'system':
        return 'System';
      default:
        return role;
    }
  };

  return (
    <div className={`chat-message ${message.role}`}>
      <div className="message-header" onClick={toggleExpand}>
        <span>{getRoleName(message.role)}</span>
        <button>{isExpanded ? 'Collapse' : 'Expand'}</button>
      </div>
      {isExpanded && (
        <div className="message-content">
          <ReactMarkdown
            components={{
              code({ node, inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                if (!inline && match && match[1] === 'plotly') {
                  return <PlotlyComponent data={String(children).replace(/\n$/, '')} />;
                }
                return <code className={className} {...props}>{children}</code>;
              }
            }}
          >
            {message.content}
          </ReactMarkdown>
          {message.details && (
            <pre className="message-details"><ReactMarkdown>{message.details}</ReactMarkdown></pre>
          )}
        </div>
      )}
    </div>
  );
}

export default ChatMessage;