from datetime import datetime
from typing import List, Dict

from marshmallow_dataclass import dataclass


@dataclass
class MessageData:
    tts: bool
    author: str
    content_history: Dict[str, str]
    embeds_url: List[str]
    channel_id: int
    channel_name: str
    attachments_url: List[str]
    guild_id: int
    created_at: datetime
    deleted: bool = False


@dataclass
class Message:
    # Hash Key
    member_id: int
    # Sort Key
    message_id: int
    # Attributes
    message_data: MessageData
