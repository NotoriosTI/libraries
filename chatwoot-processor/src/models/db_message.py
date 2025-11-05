from __future__ import annotations

import enum

from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Direction(enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class Status(enum.Enum):
    received = "received"
    queued = "queued"
    sent = "sent"
    failed = "failed"
    read = "read"


class DBMessage(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    sender = Column(String, nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    direction = Column(Enum(Direction), nullable=False)
    status = Column(Enum(Status), nullable=False, index=True)

