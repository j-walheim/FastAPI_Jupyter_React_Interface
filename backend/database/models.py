from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Conversation(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    user_id: str
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    messages: List["Message"] = Relationship(back_populates="conversation")

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.id")
    user_id: str
    message_number: int
    message_data: str
    conversation: Conversation = Relationship(back_populates="messages")
