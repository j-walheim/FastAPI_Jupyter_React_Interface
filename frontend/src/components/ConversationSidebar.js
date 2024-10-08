import React from 'react';
import './ConversationSidebar.css';

function ConversationSidebar({ conversations, onSelectConversation, currentConversationId, onNewConversation }) {
  const truncateSummary = (summary, maxLength = 30) => {
    return summary && summary.length > maxLength ? summary.substring(0, maxLength) + '...' : summary || 'No summary';
  };

  return (
    <div className="conversation-sidebar">
      <h2>Conversations</h2>
      <button onClick={onNewConversation} className="new-conversation-btn">New Conversation</button>
      <ul>
        {conversations.map((conv) => (
          <li 
            key={conv.conversation_id} 
            onClick={() => onSelectConversation(conv.conversation_id)}
            className={conv.conversation_id === currentConversationId ? 'active' : ''}
          >
            <span className="conversation-id">
              {conv.conversation_id ? conv.conversation_id.slice(0, 8) + '...' : 'No ID'}
            </span>
            <span className="conversation-summary">{truncateSummary(conv.summary)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ConversationSidebar;