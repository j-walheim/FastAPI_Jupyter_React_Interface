from sqlmodel import Field, SQLModel, UniqueConstraint, Relationship
from typing import Optional, List
from datetime import datetime

class Conversation(SQLModel, table=True):
    conversation_id: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    summary: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    messages: List["Message"] = Relationship(back_populates="conversation")

    __table_args__ = (UniqueConstraint('conversation_id', 'user_id', name='uix_conversation_id_user_id'),)

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.conversation_id")
    user_id: str
    message_number: int
    message_data: str
    conversation: Conversation = Relationship(back_populates="messages")
