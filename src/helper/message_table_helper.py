# External Modules
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from marshmallow import EXCLUDE
# My Classes
from models.message import Message

TABLE_NAME = 'DiscordBot-Messages'
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()


def put_message(client: boto3.client, message: Message):
    try:
        response = client.put_item(
            TableName=TABLE_NAME,
            Item={
                k: SERIALIZER.serialize(v) for k, v in Message.Schema().dump(message).items() if v != "" or v is not None
            }
        )
    except ClientError as err:
        raise err
    else:
        return response


def get_message(client: boto3.client, member_id, message_id):
    try:
        get_result = client.get_item(
            TableName=TABLE_NAME,
            Key={
                "member_id": {"N": str(member_id)},
                "message_id": {"N": str(message_id)}
            }
        )
    except ClientError as err:
        raise err
    else:
        if get_result.get('Item') is None:
            return None
        deserialized = {k: DESERIALIZER.deserialize(v) for k, v in get_result.get("Item").items()}
        return Message.Schema().load(deserialized, unknown=EXCLUDE)


def set_att_keys(client: boto3.client, member_id, message_id, att_name, att_value):
    try:
        print(SERIALIZER.serialize(att_value))
        response = client.update_item(
            TableName=TABLE_NAME,
            Key={
                "message_id": {"N": str(message_id)},
                "member_id": {"N": str(member_id)}
            },
            UpdateExpression="SET message_data.#ATT = :value",
            ExpressionAttributeNames={
                '#ATT': att_name
            },
            ExpressionAttributeValues={':value': SERIALIZER.serialize(att_value)}
        )
    except ClientError as err:
        raise err
    else:
        return response


def set_att(client: boto3.client, message, att_name, att_value):
    return set_att_keys(
        client=client, member_id=message.author.id, message_id=message.id, att_name=att_name, att_value=att_value)
