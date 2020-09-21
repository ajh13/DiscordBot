# External Modules
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from marshmallow import EXCLUDE
from datetime import datetime
# My Classes
from models.member import Member

TABLE_NAME = 'DiscordBot-MemberData'
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()


def put_member(client: boto3.client, member):
    try:
        response = client.put_item(
            TableName=TABLE_NAME,
            Item={
                k: SERIALIZER.serialize(v) for k, v in Member.Schema().dump(member).items() if v != "" or v is not None
            }
        )
    except ClientError as err:
        raise err
    else:
        return response


def get_member(client: boto3.client, guild_id, member_id):
    try:
        get_result = client.get_item(
            TableName=TABLE_NAME,
            Key={
                "guild_id": {"N": str(guild_id)},
                "member_id": {"N": str(member_id)}
            }
        )
    except ClientError as err:
        raise err
    else:
        if get_result.get('Item') is None:
            return None
        deserialized = {k: DESERIALIZER.deserialize(v) for k, v in get_result.get("Item").items()}
        return Member.Schema().load(deserialized, unknown=EXCLUDE)


def inc_stat_keys(client: boto3.client, guild_id, member_id, stat_name):
    try:
        response = client.update_item(
            TableName=TABLE_NAME,
            Key={
                "guild_id": {"N": str(guild_id)},
                "member_id": {"N": str(member_id)}
            },
            UpdateExpression="ADD member_stats.#MSG_COUNT :increment SET last_update_date = :date",
            ExpressionAttributeNames={
                '#MSG_COUNT': stat_name
            },
            ExpressionAttributeValues={':increment': {'N': '1'},
                                       ':date': {'S': str(datetime.now())}
                                       }
        )
    except ClientError as err:
        raise err
    else:
        return response


def inc_stat(client: boto3.client, member, stat_name):
    return inc_stat_keys(client=client, guild_id=member.guild.id, member_id=member.id, stat_name=stat_name)
