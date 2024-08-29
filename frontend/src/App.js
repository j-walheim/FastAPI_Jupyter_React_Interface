import React, { useState, useEffect, useRef } from 'react';
import CodeEditor from './components/CodeEditor';
import OutputDisplay from './components/OutputDisplay';
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
    const newConversationId = uuidv4();
    setConversationId(newConversationId);
    setInstructions('');
    setOutput('');
    setGeneratedCode('');
    if (ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ 
        type: 'new_conversation', 
        conversation_id: newConversationId
      }));
    }
  };

  useEffect(() => {
    ws.current = new WebSocket('ws://localhost:8000/ws');
    ws.current.onopen = () => {
      console.log('WebSocket Connected');
      ws.current.send(JSON.stringify({ type: 'get_conversations' }));
    };
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'chat_message') {
        setChatHistory(prevHistory => [...prevHistory, data.message]);
      } else if (data.type === 'result') {
        setOutput(data.output);
        setGeneratedCode(data.generated_code);
        setChatHistory(prevHistory => [
          ...prevHistory,
          { role: 'assistant', content: data.output, collapsible: true }
        ]);
      } else if (data.type === 'conversation_id') {
        setConversationId(data.conversation_id);
        setConversations(prevConversations => [
          ...prevConversations,
          { id: data.conversation_id, summary: 'New conversation' }
        ]);
      } else if (data.type === 'conversation_summary') {
        setConversations(prevConversations => 
          prevConversations.map(conv => 
            conv.id === data.conversation_id 
              ? { ...conv, summary: data.summary } 
              : conv
          )
        );
      } else if (data.type === 'all_conversations') {
        setConversations(data.conversations);
      } else if (data.type === 'loaded_conversation') {
        setChatHistory(data.messages);
      }
    };
    return () => {
      ws.current.close();
    };
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (ws.current.readyState === WebSocket.OPEN) {
      setChatHistory(prevHistory => [
        ...prevHistory,
        { role: 'human', content: instructions }
      ]);
      ws.current.send(JSON.stringify({ 
        type: 'execute', 
        instructions: instructions,
        conversation_id: conversationId
      }));
      setInstructions('');
    }
  };

  const handleLoadConversation = (id) => {
    setConversationId(id);
    setChatHistory([]);  // Clear the current chat history
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
        <h1>FastAPI Jupyter React Interface</h1>
        <p>Current Conversation ID: {conversationId}</p>
        <div className="chat-history">
          {chatHistory.map((msg, index) => (
            <ChatMessage
              key={index}
              message={msg}
              isLastMessage={index === chatHistory.length - 1}
            />
          ))}
        </div>
        <form onSubmit={handleSubmit}>
          <CodeEditor
            code={instructions}
            setCode={setInstructions}
            placeholder="Enter instructions here"
          />
          <button type="submit">Generate and Execute Code</button>
        </form>
        <div>
          <h2>Generated Code:</h2>
          <pre>{generatedCode}</pre>
        </div>
        <OutputDisplay output={output} />
      </div>
    </div>
  );
}

export default App;
