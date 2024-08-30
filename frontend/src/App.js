import React, { useState, useEffect, useRef } from 'react';
import CodeEditor from './components/CodeEditor';
import ConversationSidebar from './components/ConversationSidebar';
import { v4 as uuidv4 } from 'uuid';
import './App.css';
import ChatMessage from './components/ChatMessage';

function App() {
  const [instructions, setInstructions] = useState('create a survival plot for IO vs. Chemo and save it as survival.png');
  const [output, setOutput] = useState('');
  const [generatedCode, setGeneratedCode] = useState('');
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
            break;
          case 'loaded_conversation':
            setChatHistory(data.data.history);
            setConversationId(data.data.id);
            break;
          case 'new_conversation':
            setConversationId(data.data.conversation_id);
            setConversations(prevConversations => [
              { id: data.data.conversation_id, summary: 'New conversation' },
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
  }, [conversationId]);

  const handleSubmit = (e) => {
    e.preventDefault();
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
    setChatHistory([]);
    if (ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ 
        type: 'load_conversation', 
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
        <div className="chat-history">
          {chatHistory.length > 0 ? (
            chatHistory.map((msg, index) => (
              <ChatMessage
                key={index}
                message={msg}
                isLastMessage={index === chatHistory.length - 1}
              />
            ))
          ) : (
            <p>No messages in this conversation yet.</p>
          )}
        </div>
        <form onSubmit={handleSubmit}>
          <CodeEditor
            code={instructions}
            setCode={setInstructions}
            placeholder="Enter instructions here"
          />
          <button type="submit">Generate and Execute Code</button>
        </form>
      </div>
    </div>
  );
}

export default App;
