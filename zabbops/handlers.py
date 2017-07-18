"""
Handlers contains useful Lambda handlers for Amazon AWS events.
"""

from base64 import b64decode
from json import loads

def KinesisStreamHandler(lambda_handler):
    """
    KinesisStreamHandler wraps any Lambda Function handler that expects a
    CloudWatch Event as input so it can instead accept a batch of records from a
    Kinesis Stream.
    """

    def handler(event, context):
        """
        Wrapper function to split a Kinesis Stream event batch into multiple
        discrete events for lambda.
        """

        for record in event['Records']:
            data = b64decode(record['kinesis']['data'])
            revent = loads(data)
            lambda_handler(revent, context)

        return {
            'message': 'Processed {} records'.format(len(event['Records']))
        }

    return handler
