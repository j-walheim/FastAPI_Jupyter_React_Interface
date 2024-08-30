from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict
from datetime import datetime
from sqlalchemy import JSON  # or JSONB, depending on your database
from sqlalchemy import Column
import json
import uuid

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.id")
    user_id: str
    message_number: int
    message_data: str  # This will store the JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)

    conversation: "Conversation" = Relationship(back_populates="messages")

    def set_message_data(self, data: dict):
        self.message_data = json.dumps(data)

    def get_message_data(self) -> dict:
        return json.loads(self.message_data)

class Conversation(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    messages: List["Message"] = Relationship(back_populates="conversation")