"""
Database Schemas for Long-Distance Companion App

Each Pydantic model maps to a MongoDB collection using the lowercase
of the class name (e.g., Room -> "room").
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class Room(BaseModel):
    code: str = Field(..., description="Shared room code between partners")
    title: Optional[str] = Field(None, description="Room title or couple name")

class Countdown(BaseModel):
    room_code: str = Field(..., description="Room code this countdown belongs to")
    target_iso: str = Field(..., description="ISO string for target date/time")

class Motd(BaseModel):
    room_code: str = Field(..., description="Room code")
    text: str = Field(..., min_length=1, max_length=500)
    author: Optional[str] = Field(None, description="Sender name or emoji")
    at: Optional[datetime] = None

class Ping(BaseModel):
    room_code: str = Field(...)
    note: Optional[str] = Field(None, max_length=140)
    author: Optional[str] = None
    at: Optional[datetime] = None

class Todo(BaseModel):
    room_code: str = Field(...)
    text: str = Field(..., min_length=1, max_length=200)
    done: bool = False
    created_at: Optional[datetime] = None
