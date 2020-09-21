# External Modules
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from marshmallow import EXCLUDE
# My Classes
from models.voice import VoiceState

TABLE_NAME = 'DiscordBot-VoiceState'
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()


def put_voice(client: boto3.client, voice_state):
    try:
        response = client.put_item(
            TableName=TABLE_NAME,
            Item={
                k: SERIALIZER.serialize(v) for k, v in VoiceState.Schema().dump(voice_state).items() if v != "" or v is not None
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
            voice = VoiceState.Schema().load(item, unknown=EXCLUDE, partial=True)
            print(voice)
            # deserialized = {k: DESERIALIZER.deserialize(v) for k, v in item}
            # voice_state_dict[deserialized.get('date_time')] = deserialized
        print(voice_state_dict)
        return voice_state_dict

        # deserialized = {k: DESERIALIZER.deserialize(v) for k, v in get_result.get("Item").items()}
        # return VoiceState.Schema().load(deserialized, unknown=EXCLUDE)