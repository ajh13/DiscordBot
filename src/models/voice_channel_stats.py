from marshmallow_dataclass import dataclass


@dataclass
class VoiceChannelStats:
    channel_id: int
    channel_name: str
    minutes_in_channel: int = 0
    joined_count: int = 0
    last_joined: int = None
    last_left: int = None
