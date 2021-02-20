import logging
import sys
from collections import OrderedDict
from datetime import datetime

import boto3
import discord
from discord import DMChannel
from discord.ext import commands
from discord.utils import get

import helper.member_table_helper as MemberTableHelper
import helper.message_table_helper as MessageTableHelper
import helper.voice_table_helper as VoiceTableHelper
from models.member import Member
from models.message import Message, MessageData
from models.voice import VoiceState

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
IS_DEV = False
BOT_TOKEN_FILE_PATH = 'configuration/bot_token.txt'
DEV_BOT_TOKEN_FILE_PATH = 'configuration/dev_bot_token.txt'
DDB = boto3.client('dynamodb')

client = commands.Bot(command_prefix=BOT_PREFIX, intents=discord.Intents.all())

# If dev in argument 1 program will not post to dynamoDB
if len(sys.argv) >= 2 and sys.argv[1] == 'dev':
    IS_DEV = True


@client.event
async def on_ready():
    print('Logged in as: ' + client.user.name)
    for guild in client.guilds:
        for server_member in guild.members:
            existing_member = MemberTableHelper.get_member(DDB, server_member.guild.id, server_member.id)
            if existing_member is None:
                new_member = Member(guild_id=server_member.guild.id,
                                    member_id=server_member.id,
                                    member_name=server_member.name)
                if not IS_DEV:
                    MemberTableHelper.put_member(DDB, new_member)
                    print(f'Added member to DDB: {new_member}')
    print('Ready for requests!')


@client.event
async def on_member_join(member):
    await member.send(f'Welcome to the server :)')
    print(member.guild.roles)
    role = get(member.guild.roles, name=STARTING_ROLE)
    await member.add_roles(role)
    print(f'{member} was given {role}')
    channel = get(member.guild.channels, name=GENERAL_CHANNEL)
    await channel.send(f'Welcome {member.mention} to {member.guild.name}!')
    existing_member = MemberTableHelper.get_member(DDB, member.guild.id, member.id)
    if existing_member is None:
        new_member = Member(guild_id=member.guild.id, member_id=member.id, member_name=member.name)
        if not IS_DEV:
            MemberTableHelper.put_member(DDB, new_member)
            print('Added member to DDB: {new_member}')
    else:
        print(f'Member isn\'t new: {existing_member}')


@client.event
async def on_member_remove(member):
    channel = get(member.guild.channels, name=GENERAL_CHANNEL)
    await channel.send(f'{member.mention} left the {member.guild.name}!')

    existing_member = MemberTableHelper.get_member(DDB, member.guild.id, member.id)
    existing_member.active = False
    if not IS_DEV:
        MemberTableHelper.put_member(DDB, existing_member)
    print(f'Member has left discord server: {existing_member}')


@client.event
async def on_voice_state_update(member, before, after):
    channel_name = None
    channel_id = None
    member_ids_in_channel = None
    if after.channel is None:
        print(f'{member.name}: Left Channel {before.channel.name}.')
    else:
        channel_name = after.channel.name
        channel_id = after.channel.id
        member_ids_in_channel = [member.id for member in after.channel.members]
        print(f'{member.name}: Joined {after.channel.name}.')
    voice_state = VoiceState(
        member_id=member.id, date_time=str(datetime.now()), deaf=after.deaf, mute=after.mute, self_mute=after.self_mute,
        self_deaf=after.self_deaf, self_stream=after.self_stream, self_video=after.self_video, afk=after.afk,
        channel_name=channel_name, channel_id=channel_id,
        member_ids_in_channel=member_ids_in_channel)
    if not IS_DEV:
        response = VoiceTableHelper.put_voice(client=DDB, voice_state=voice_state)
        print(response)


@client.event
async def on_message(message):
    if isinstance(message.channel, DMChannel):
        return
    print(f'Message from {message.author}: {message.content}')

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
    if not IS_DEV:
        MessageTableHelper.put_message(client=DDB, message=new_message)
        MemberTableHelper.inc_stat(client=DDB, member=message.author, stat_name='messages_sent_count')

    await client.process_commands(message)


@client.event
async def on_raw_message_delete(payload):
    # Broken still need to find way to reference a member from a deleted message
    print(f'deleted: {payload.message_id}')
    if payload.cached_message:
        print(payload)
        if not IS_DEV:
            MessageTableHelper.set_att_keys(client=DDB, member_id=payload.cached_message.author.id,
                                            message_id=payload.message_id, att_name='deleted', att_value=True)
            MemberTableHelper.inc_stat_keys(client=DDB, guild_id=payload.guild_id,
                                            member_id=payload.cached_message.author.id,
                                            stat_name='messages_deleted_count')


@client.event
async def on_raw_message_edit(payload):
    print(payload)
    channel = await client.fetch_channel(payload.data.get('channel_id'))
    message = await channel.fetch_message(payload.message_id)
    author = message.author
    content = payload.data.get('content')
    ddb_message = MessageTableHelper.get_message(client=DDB, member_id=author.id, message_id=payload.message_id)
    ddb_message.message_data.content_history[str(payload.data.get('edited_timestamp'))] = content
    if not IS_DEV:
        MemberTableHelper.inc_stat_keys(client=DDB,
                                        guild_id=payload.data.get('guild_id'),
                                        member_id=author.id,
                                        stat_name='messages_edited_count')
        MessageTableHelper.set_att_keys(client=DDB,
                                        member_id=author.id,
                                        message_id=payload.message_id,
                                        att_name='content_history',
                                        att_value=ddb_message.message_data.content_history)
    print(f'{author.name}({author.id}) edited: {payload.message_id} channel:{channel.name} : {content}')


@client.event
async def on_raw_reaction_add(payload):
    if not IS_DEV:
        MemberTableHelper.inc_stat_keys(
            client=DDB, guild_id=payload.guild_id, member_id=payload.user_id, stat_name='reactions_added_count')
    print(f'{payload.user_id} added reaction: {payload.emoji} on {payload.message_id}')


@client.event
async def on_raw_reaction_remove(payload):
    if not IS_DEV:
        MemberTableHelper.inc_stat_keys(
            client=DDB, guild_id=payload.guild_id, member_id=payload.user_id, stat_name='reactions_removed_count')
    print('{payload.user_id} removed reaction: {payload.emoji} on {payload.message_id}')


@client.event
async def on_user_update(before, after):
    if before.avatar != after.avatar:
        print(f'{after.name} updated avatar from {before.avatar_url} to {after.avatar_url}')
    if before.username != after.username:
        print(f'{before.username} changed username to {after.username}')
    print('User updated')


@client.event
async def on_member_ban(guild, user):
    print(f'{user.name} has been banned from {guild.name}')
    ban = await guild.fetch_ban(user)
    print(ban)


@client.event
async def on_member_unban(guild, member):
    print(f'{member.name} has been unbanned from {guild.name}')


@client.command()
async def stats(ctx):
    existing_member = MemberTableHelper.get_member(DDB, ctx.guild.id, ctx.author.id)
    in_voice_time = VoiceTableHelper.get_time_in_voice(DDB, ctx.author.id, ctx.author.guild)
    member_stats = existing_member.member_stats
    message = f'```\n' \
              f'{ctx.guild.name} Stats:\n' \
              f'Message Sent: {member_stats.messages_sent_count}\n' \
              f'Messages Edited: {member_stats.messages_edited_count}\n' \
              f'Messages Deleted: {member_stats.messages_deleted_count}\n' \
              f'Reactions Added: {member_stats.reactions_added_count}\n' \
              f'Reactions Removed: {member_stats.reactions_removed_count}\n' \
              f'Time in Voice Channels: {in_voice_time}\n' \
              f'```'
    print(f'{ctx.author.name}:\n{message}')
    await ctx.author.send(content=message)


@client.command()
async def voice_leaderboard(ctx):
    bot_msg = await ctx.channel.send(content=f'```\nProcessing request from {ctx.author.name}, please wait.```')
    top_x = 10
    for x in ctx.message.content.split(' '):
        if x.find('top') != -1:
            number = x.split('top')[1]
            try:
                number = int(number)
                top_x = number
            except Exception:
                top_x = top_x

    members = MemberTableHelper.get_members(DDB, ctx.guild.id)
    time_to_member = {}
    for member in members:
        voice = VoiceTableHelper.get_time_in_voice(DDB, member.member_id, ctx.author.guild)
        time_to_member[voice] = member
    ordered_time = OrderedDict(sorted(time_to_member.items(), reverse=True))
    message = '```\nTime spent in voice channel leaderboard:\n'
    i = 0
    for k, v in ordered_time.items():
        i += 1
        message += f'{i}) {v.member_name}: {k}\n'
        if i == top_x:
            break
    message += '```'
    await bot_msg.edit(content=message)


def main():
    with open(DEV_BOT_TOKEN_FILE_PATH if IS_DEV else BOT_TOKEN_FILE_PATH) as file:
        client.run(file.read())


if __name__ == "__main__":
    main()

# Things to implement:
# How much time streamed/playing a game based on discord activity
