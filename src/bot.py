# Public Libraries
from discord.ext import commands
from discord.utils import get
import logging
import boto3
from datetime import datetime
import random
# My classes
from models.member import Member
from models.message import Message, MessageData
from models.voice import VoiceState
import src.helper.member_table_helper as MemberTableHelper
import src.helper.message_table_helper as MessageTableHelper
import src.helper.voice_table_helper as VoiceTableHelper

ddb = boto3.client('dynamodb')
# Set the logging configuration for discord.py
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)
# Secret token that for the bot
BOT_PREFIX = '$'
STARTING_ROLE = 'Friend'
GENERAL_CHANNEL = 'general'
MEMBER_DIR = 'member_data/'

client = commands.Bot(command_prefix=BOT_PREFIX)


@client.event
async def on_ready():
    print("Logged in as: " + client.user.name + "\n")
    for guild in client.guilds:
        for server_member in guild.members:
            existing_member = MemberTableHelper.get_member(ddb, server_member.guild.id, server_member.id)
            if existing_member is None:
                new_member = Member(guild_id=server_member.guild.id,
                                    member_id=server_member.id,
                                    member_name=server_member.name)
                MemberTableHelper.put_member(ddb, new_member)
                print("Added member to DDB: ", new_member)
            else:
                print("Member isn't new: ", existing_member)


@client.event
async def on_member_join(member):
    role = get(member.guild.roles, name=STARTING_ROLE)
    await member.add_roles(role)
    print(f"{member} was given {role}")
    channel = get(member.guild.channels, name=GENERAL_CHANNEL)
    await channel.send(f"Welcome {member.mention} to the {member.guild.name}!")
    existing_member = MemberTableHelper.get_member(ddb, member.guild.id, member.id)
    if existing_member is None:
        new_member = Member(guild_id=member.guild.id, member_id=member.id, member_name=member.name)
        MemberTableHelper.put_member(ddb, new_member)
        print("Added member to DDB: ", new_member)
    else:
        print("Member isn't new: ", existing_member)


@client.event
async def on_member_remove(member):
    channel = get(member.guild.channels, name=GENERAL_CHANNEL)
    await channel.send(f"{member.mention} left the {member.guild.name}!")

    existing_member = MemberTableHelper.get_member(ddb, member.guild.id, member.id)
    existing_member.active = False
    MemberTableHelper.put_member(ddb, existing_member)
    print("Member has left discord server: ", existing_member)


@client.event
async def on_member_remove(guild, member):
    channel = get(guild.channels, name=GENERAL_CHANNEL)
    await channel.send(f"{member.mention} has been banned from {guild.name}!")


@client.event
async def on_voice_state_update(member, before, after):
    channel_name = None
    channel_id = None
    member_ids_in_channel = None
    if after.channel is None:
        print(f"{member.name}: Left Channel {before.channel.name}.")
    else:
        channel_name = after.channel.name
        channel_id = after.channel.id
        member_ids_in_channel = [member.id for member in after.channel.members]
        print(f"{member.name}: Joined {after.channel.name}.")
    voice_state = VoiceState(
        member_id=member.id, date_time=str(datetime.now()), deaf=after.deaf, mute=after.mute, self_mute=after.self_mute,
        self_deaf=after.self_deaf, self_stream=after.self_stream, self_video=after.self_video, afk=after.afk,
        channel_name=channel_name, channel_id=channel_id,
        member_ids_in_channel=member_ids_in_channel)
    response = VoiceTableHelper.put_voice(client=ddb, voice_state=voice_state)
    print(response)
    # Triggered when member leaves all voice channels


@client.event
async def on_message(message):
    """Triggered whenever anyone chats don't record for bot chatting"""
    if message.author == client.user:
        return

    print('Message from {0.author}: {0.content}'.format(message))

    message_data = MessageData(tts=message.tts,
                               author=message.author.name,
                               content_history={str(message.created_at): message.content},
                               embeds_url=[embed.url for embed in message.embeds],
                               channel_id=message.channel.id,
                               channel_name=message.channel.name,
                               attachments_url=[attachment.url for attachment in message.attachments],
                               guild_id=message.guild.id,
                               created_at=message.created_at)
    new_message = Message(member_id=message.author.id, message_id=message.id, message_data=message_data)
    MessageTableHelper.put_message(client=ddb, message=new_message)
    MemberTableHelper.inc_stat(client=ddb, member=message.author, stat_name='messages_sent_count')

    await client.process_commands(message)


@client.event
async def on_raw_message_delete(payload):
    # Broken still need to find way to reference a member from a deleted message
    print(f"deleted: {payload.message_id}")
    if payload.cached_message:
        print(payload)
        MessageTableHelper.set_att_keys(client=ddb, member_id=payload.cached_message.author.id, message_id=payload.message_id, att_name='deleted', att_value=True)
        MemberTableHelper.inc_stat_keys(client=ddb, guild_id=payload.guild_id, member_id=payload.cached_message.author.id, stat_name='messages_deleted_count')


@client.event
async def on_raw_message_edit(payload):
    author_id = payload.data.get('author').get('id')
    content = payload.data.get('content')
    ddb_message = MessageTableHelper.get_message(client=ddb, member_id=author_id, message_id=payload.message_id)
    ddb_message.message_data.content_history[str(payload.data.get('edited_timestamp'))] = content
    MemberTableHelper.inc_stat_keys(client=ddb,
                                    guild_id=payload.data.get('guild_id'),
                                    member_id=author_id,
                                    stat_name='messages_edited_count')
    MessageTableHelper.set_att_keys(client=ddb,
                                    member_id=author_id,
                                    message_id=payload.message_id,
                                    att_name='content_history',
                                    att_value=ddb_message.message_data.content_history)
    print(f"{author_id} edited: {payload.message_id}: {content}")


@client.event
async def on_raw_reaction_add(payload):
    MemberTableHelper.inc_stat_keys(
        client=ddb, guild_id=payload.guild_id, member_id=payload.user_id, stat_name='reactions_added_count')
    print(f"{payload.user_id} added reaction: {payload.emoji} on {payload.message_id}")


@client.event
async def on_raw_reaction_remove(payload):
    MemberTableHelper.inc_stat_keys(
        client=ddb, guild_id=payload.guild_id, member_id=payload.user_id, stat_name='reactions_removed_count')
    print(f"{payload.user_id} removed reaction: {payload.emoji} on {payload.message_id}")


@client.event
async def on_user_update(before, after):
    if before.avatar != after.avatar:
        print(f"{after.name} updated avatar from {before.avatar_url} to {after.avatar_url}")
    if before.username != after.username:
        print(f"{before.username} changed username to {after.username}")
    print("User updated")


@client.event
async def on_member_ban(guild, user):
    print(f"{user.name} has been banned from {guild.name}")
    ban = await guild.fetch_ban(user)
    print(ban)


@client.event
async def on_member_unban(guild, member):
    print(f"{member.name} has been unbanned from {guild.name}")


@client.command()
async def stats(ctx):
    existing_member = MemberTableHelper.get_member(ddb, ctx.guild.id, ctx.author.id)
    member_stats = existing_member.member_stats
    print(existing_member)
    message = f"```\n" \
              f"{ctx.guild.name} Stats:\n" \
              f"Message Sent: {member_stats.messages_sent_count}\n" \
              f"Messages Edited: {member_stats.messages_edited_count}\n" \
              f"Messages Deleted: {member_stats.messages_deleted_count}\n" \
              f"Reactions Added: {member_stats.reactions_added_count}\n" \
              f"Reactions Removed: {member_stats.reactions_removed_count}\n" \
              f"```"
    await ctx.author.send(content=message)
    # voice_stats = {}
    # voice_states = VoiceTableHelper.batch_get_voice(client=ddb, member_id=ctx.author.id)
    # for date_time, voice_state in sorted(voice_states.iteritems()):


with open('configuration/bot_token.txt') as file:
    client.run(file.read())

# Things to implement:
# How much time streamed/playing a game based on discord activity
