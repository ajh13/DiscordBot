from datetime import datetime

from marshmallow_dataclass import dataclass


@dataclass
class MemberStats:
    minutes_in_voice: int = 0
    messages_sent_count: int = 0
    messages_edited_count: int = 0
    messages_deleted_count: int = 0
    started_typing_count: int = 0
    reactions_added_count: int = 0
    reactions_removed_count: int = 0


@dataclass
class Member:
    # Hash Key
    guild_id: int
    # Sort Key
    member_id: int
    # Attributes
    member_name: str
    active: bool = True
    member_stats: MemberStats = MemberStats()
    create_date: str = str(datetime.now())
    last_update_date: str = str(datetime.now())
