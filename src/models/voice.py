from dataclasses import field
from typing import List

from marshmallow_dataclass import dataclass


@dataclass
class VoiceState:
    member_id: int
    date_time: str
    deaf: bool
    mute: bool
    self_mute: bool
    self_deaf: bool
    self_stream: bool
    self_video: bool
    afk: bool
    channel_name: str = None
    channel_id: str = None
    member_ids_in_channel: List[str] = field(default_factory=list)
