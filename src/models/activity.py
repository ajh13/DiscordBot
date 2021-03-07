from datetime import datetime

from marshmallow_dataclass import dataclass
from discord import Activity


@dataclass
class Activity:

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
