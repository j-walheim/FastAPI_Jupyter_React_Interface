import React, { useState, useEffect, useRef } from 'react';
import ChatInput from './components/ChatInput';
import ConversationSidebar from './components/ConversationSidebar';
import './App.css';
import ChatMessage from './components/ChatMessage';

function App() {
  const [instructions, setInstructions] = useState('create a survival plot for IO vs. Chemo and save it as survival.png');
  const [conversationId, setConversationId] = useState('');
  const [conversations, setConversations] = useState([]);
  const [chatHistory, setChatHistory] = useState([]);
  const ws = useRef(null);

  const handleNewConversation = () => {
    if (ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ 
        type: 'meta',
        action: 'new_conversation'
      }));
    }
  };

  const requestConversations = () => {
    if (ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ 
        type: 'meta',
        action: 'get_conversations'
      }));
    }
  };

  useEffect(() => {
    ws.current = new WebSocket('ws://localhost:8000/ws');
    ws.current.onopen = () => {
      console.log('WebSocket Connected');
      requestConversations();
    };
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Received message:', data);
      console.log('Received data type:', data.type, 'Action:', data.action || 'N/A');
      
      if (data.type === 'chat_message') {
        setChatHistory(prevHistory => [...prevHistory, data.message]);
      } else if (data.type === 'meta') {
        switch (data.action) {
          case 'conversations':
            setConversations(data.data.reverse());
            if (data.data.length > 0 && !conversationId) {
              handleLoadConversation(data.data[0].conversation_id);
            }
            break;
          case 'conversation_info':
            setConversationId(data.data.id);
            setChatHistory([]);
            break;
          case 'conversation_loaded':
            console.log('Conversation fully loaded');
            break;
          case 'new_conversation':
            setConversationId(data.data.conversation_id);
            setConversations(prevConversations => [
              { conversation_id: data.data.conversation_id, summary: data.data.summary },
              ...prevConversations
            ]);
            setChatHistory([]);
            break;
          default:
            console.warn('Unknown meta action:', data.action);
        }
      } else {
        console.warn('Unknown message type:', data.type);
      }
    };
    return () => {
      ws.current.close();
    };
  }, []); // Empty dependency array ensures this runs only once on mount
  const handleSubmit = () => {
    if (ws.current.readyState === WebSocket.OPEN) {
      setChatHistory(prevHistory => [
        ...prevHistory,
        { role: 'human', content: instructions }
      ]);
      ws.current.send(JSON.stringify({ 
        type: 'message',
        message: instructions,
        conversation_id: conversationId
      }));
      setInstructions('');
    }
  };

  const handleLoadConversation = (id) => {
    console.log('Loading conversation:', id);
    setConversationId(id);
    if (ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ 
        type: 'meta',
        action: 'load_conversation',
        conversation_id: id
      }));
    }
  };

  return (
    <div className="App">
      <ConversationSidebar 
        conversations={conversations}
        onSelectConversation={handleLoadConversation}
        currentConversationId={conversationId}
        onNewConversation={handleNewConversation}
      />
      <div className="main-content">
        <h1>React - FastAPI - Coding Agent</h1>
        <p>Current Conversation ID: {conversationId}</p>
        <div className="chat-container">
          <div className="chat-history">
            {chatHistory.length > 0 ? (
              chatHistory.map((msg, index) => (
                <ChatMessage
                  key={index}
                  message={msg}
                  isLastMessage={index === chatHistory.length - 1}
                  isUserMessage={msg.role === 'human'}
                />
              ))
            ) : (
              <p>No messages in this conversation yet.</p>
            )}
          </div>
          <ChatInput
            message={instructions}
            setMessage={setInstructions}
            onSend={handleSubmit}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
