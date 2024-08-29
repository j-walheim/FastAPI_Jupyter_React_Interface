import React from 'react';
import './ConversationSidebar.css';

function ConversationSidebar({ conversations, onSelectConversation, currentConversationId }) {
  return (
    <div className="conversation-sidebar">
      <h2>Conversations</h2>
      <ul>
        {conversations.map((conv) => (
          <li 
            key={conv.id} 
            onClick={() => onSelectConversation(conv.id)}
            className={conv.id === currentConversationId ? 'active' : ''}
          >
            <span className="conversation-id">{conv.id.slice(0, 8)}...</span>
            <span className="conversation-summary">{conv.summary}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ConversationSidebar;