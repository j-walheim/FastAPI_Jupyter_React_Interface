import asyncio
import uuid
from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlmodel import Session
from database.operations import get_session
from core.chat_manager import ChatManager
from utils.connection_manager import WebSocketConnectionManager, connection_manager
from database.operations import ConversationMemory

async def websocket_endpoint(websocket: WebSocket, session: Session = Depends(get_session)):
    client_id = str(uuid.uuid4())
    await connection_manager.connect(websocket, client_id)
    
    user_id = "test_user"


    message_queue = asyncio.Queue()
    asyncio.create_task(process_queue(message_queue, websocket))    
                    
    try:
        while True:
            data = await websocket.receive_json()
            print(f"Received data: {data}")
            
            if data['type'] == 'message':
                instructions = data['message']
                conversation_id = data['conversation_id']
                history = ConversationMemory.get_conversation_history(session, conversation_id, user_id)

                chat_manager = ChatManager(message_queue)
                                
                await chat_manager.chat(instructions, history, conversation_id, user_id, session)
                
            elif data['type'] == 'meta':
                if data['action'] == 'get_conversations':
                    print("Fetching conversations")
                    conversations = ConversationMemory.get_all_conversations(session, user_id)
                    print(f"Found {len(conversations)} conversations")
                    await message_queue.put({
                        'type': 'meta',
                        'action': 'conversations',
                        'data': conversations
                    })

                elif data['action'] == 'load_conversation':
                    conversation_id = data['conversation_id']
                    history = ConversationMemory.get_conversation_history(session, conversation_id, user_id)
                    summary = ConversationMemory.get_summary(session, conversation_id)
                    
                    print(f"Loading conversation: {conversation_id}")
                    print(f"History length: {len(history)}")
                    
                    await message_queue.put({
                        'type': 'meta',
                        'action': 'conversation_info',
                        'data': {
                            'id': conversation_id,
                            'summary': summary
                        }
                    })
                    
                    for msg_number, msg_data in history:
                        try:
                            parsed_msg = msg_data
                            message_content = parsed_msg['message']['content']

                            await message_queue.put({
                                'type': 'chat_message',
                                'message': {
                                    'role': parsed_msg['message']['role'],
                                    'content': message_content
                                }
                            })
                            print(f"  Queued message {msg_number}: Role: {parsed_msg['message']['role']}, Content: {message_content[:50]}...")
                        except Exception as e:
                            print(f"  Error queueing message {msg_number}: {e}")
                            print(f"  Raw message data: {msg_data}")
                    
                    await message_queue.put({
                        'type': 'meta',
                        'action': 'conversation_loaded'
                    })
                    
                elif data['action'] == 'new_conversation':
                    new_conversation_id = str(uuid.uuid4())
                    ConversationMemory.create_new_conversation(session, user_id, new_conversation_id)
                    await message_queue.put({
                        'type': 'meta',
                        'action': 'new_conversation',
                        'data': {
                            'conversation_id': new_conversation_id
                        }
                    })

    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)

async def process_queue(queue: asyncio.Queue, websocket: WebSocket):
    while True:
        message = await queue.get()
        await connection_manager.send_message(message, websocket)
        queue.task_done()
