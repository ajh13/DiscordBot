from datetime import datetime, timedelta

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from botocore.exceptions import ClientError
from marshmallow import EXCLUDE

from models.voice import VoiceState

TABLE_NAME = 'DiscordBot-VoiceState'
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()


def put_voice(client: boto3.client, voice_state):
    try:
        response = client.put_item(
            TableName=TABLE_NAME,
            Item={
                k: SERIALIZER.serialize(v) for k, v in VoiceState.Schema().dump(voice_state).items() if
                v != '' or v is not None
            }
        )
    except ClientError as err:
        raise err
    else:
        return response


def batch_get_voice(client: boto3.client, member_id):
    dynamodb = boto3.resource('dynamodb')
    try:
        table = dynamodb.Table(TABLE_NAME)
        result = table.query(
            KeyConditionExpression=Key('member_id').eq(member_id)
        )
    except ClientError as err:
        raise err
    else:
        voice_state_dict = {}
        if result.get('Items') is None:
            return None
        for item in result.get('Items'):
            if item.get('member_ids_in_channel') is None:
                item['member_ids_in_channel'] = []
            voice = VoiceState.Schema().load(item, unknown=EXCLUDE, partial=True)
            voice_state_dict[voice.date_time] = voice

            # deserialized = {k: DESERIALIZER.deserialize(v) for k, v in item}
            # voice_state_dict[deserialized.get('date_time')] = deserialized
        return voice_state_dict

        # deserialized = {k: DESERIALIZER.deserialize(v) for k, v in get_result.get('Item').items()}
        # return VoiceState.Schema().load(deserialized, unknown=EXCLUDE)


def get_time_in_voice(client: boto3.client, member_id, guild):
    afk_channel_id = guild.afk_channel.id
    voice_data = batch_get_voice(client, member_id)
    time = None
    time_in_voice = timedelta(0)
    time_afk = None
    time_in_afk = timedelta(0)
    for dt, voice in voice_data.items():
        if voice.channel_id is not None and int(voice.channel_id) == afk_channel_id:
            if time_afk is None:
                time_afk = datetime.strptime(voice.date_time, '%Y-%m-%d %H:%M:%S.%f')
        elif (voice.channel_id is None or int(voice.channel_id) != afk_channel_id) and time_afk is not None:
            curr_afk_time = datetime.strptime(voice.date_time, '%Y-%m-%d %H:%M:%S.%f')
            time_in_afk = time_in_afk + (curr_afk_time - time_afk)
            time_afk = None

        if voice.channel_id is not None:
            if time is None:
                time = datetime.strptime(voice.date_time, '%Y-%m-%d %H:%M:%S.%f')
        elif voice.channel_id is None and time is not None:
            curr_time = datetime.strptime(voice.date_time, '%Y-%m-%d %H:%M:%S.%f')
            time_in_voice = time_in_voice + (curr_time - time)
            time = None
    time_in_voice = time_in_voice - time_in_afk
    time_in_voice = time_in_voice - timedelta(microseconds=time_in_voice.microseconds)

    return time_in_voice
