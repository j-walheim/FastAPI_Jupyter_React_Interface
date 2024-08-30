import json
from datetime import datetime
from sqlmodel import Session, select, create_engine, SQLModel
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
    def add_message(session: Session, user_id: str, conversation_id: str, message_number: int, message_data: dict):
        conversation = session.exec(select(Conversation).where(Conversation.id == conversation_id)).first()
        if not conversation:
            conversation = Conversation(id=conversation_id, user_id=user_id)
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
        
        message = Message(
            conversation_id=conversation_id,
            user_id=user_id,
            message_number=message_number,
            message_data=json.dumps(message_data)
        )
        session.add(message)
        session.commit()

    @staticmethod
    def get_conversation_history(session: Session, conversation_id: str, user_id: str):
        messages = session.exec(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.message_number)).all()
        return [(message.message_number, json.loads(message.message_data)) for message in messages]

    @staticmethod
    def update_summary(session: Session, user_id: str, summary: str):
        conversation = session.exec(select(Conversation).where(Conversation.user_id == user_id)).first()
        if conversation:
            conversation.summary = summary
            conversation.updated_at = datetime.utcnow()
            session.commit()

    @staticmethod
    def get_summary(session: Session, conversation_id: str):
        conversation = session.exec(select(Conversation).where(Conversation.id == conversation_id)).first()
        return conversation.summary if conversation else None

    @staticmethod
    def get_all_conversations(session: Session, user_id: str):
        conversations = session.exec(select(Conversation).where(Conversation.user_id == user_id)).all()
        return [{'id': conv.id, 'summary': conv.summary or 'No summary available'} for conv in conversations]

    @staticmethod
    def create_new_conversation(session: Session, user_id: str, conversation_id: str):
        conversation = Conversation(id=conversation_id, user_id=user_id)
        session.add(conversation)
        session.commit()
        return conversation
