import json
from datetime import datetime
from sqlmodel import Session, select, create_engine, SQLModel
from sqlalchemy import and_  # Add this import
from .models import Message, Conversation
from utils.helpers import print_verbose
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./sql_app.db")
engine = create_engine(DATABASE_URL)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

class ConversationMemory:
    @staticmethod
    def add_message(session: Session, user_id: str, conversation_id: str, message_data: dict):
        conversation = session.exec(select(Conversation).where(Conversation.conversation_id == conversation_id)).first()
        if not conversation:
            conversation = Conversation(conversation_id=conversation_id, user_id=user_id)
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
        
        # Get the current message count for this conversation
        message_count = session.exec(select(Message.message_number).where(Message.conversation_id == conversation_id).order_by(Message.message_number.desc())).first()
        message_number = (message_count or 0) + 1
        
        message = Message(
            conversation_id=conversation_id,
            user_id=user_id,
            message_number=message_number,
            message_data=json.dumps(message_data)
        )
        session.add(message)
        session.commit()
        return message_number

    @staticmethod
    def get_conversation_history(session: Session, conversation_id: str, user_id: str):
        messages = session.exec(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.message_number)).all()
        return [(message.message_number, json.loads(message.message_data)) for message in messages]

    @staticmethod
    def update_summary(session: Session, conversation_id: str, user_id: str, summary: str):
        conversation = session.exec(select(Conversation).where(
            and_(Conversation.conversation_id == conversation_id, Conversation.user_id == user_id)
        )).first()
        if conversation:
            conversation.summary = summary
            conversation.updated_at = datetime.utcnow()
            session.commit()
        else:
            print_verbose(f"Conversation not found for conversation_id: {conversation_id} and user_id: {user_id}")

    @staticmethod
    def get_summary(session: Session, conversation_id: str, user_id: str):
        conversation = session.exec(select(Conversation).where(
            and_(Conversation.conversation_id == conversation_id, Conversation.user_id == user_id)
        )).first()
        return conversation.summary if conversation else None

    @staticmethod
    def get_all_conversations(session: Session, user_id: str):
        conversations = session.exec(select(Conversation).where(Conversation.user_id == user_id)).all()
        return [{'conversation_id': conv.conversation_id, 'summary': conv.summary or 'No summary available'} for conv in conversations]

    @staticmethod
    def create_new_conversation(session: Session, user_id: str, conversation_id: str):
        conversation = Conversation(conversation_id=conversation_id, user_id=user_id)
        session.add(conversation)
        session.commit()
        return conversation
