# Lambda_handler function to process AWS Inspector SNS messages
#   1) Filter out unwanted messages/message to be skipped
#   2) Call the appropriate message type parser. Returns: Slack channel, subject, message
#   3) (optional) create an email subscription on outbound SNS topic
#   4) publish human readable message on outbound SNS topic 

# generic imports
from __future__ import print_function
import boto3
import json
import datetime
import sys
import os

sns = boto3.client('sns')

# parsers for SNS message types
from parsers import started
from parsers import completed
from parsers import finding

# quick function to handle datetime serialization problems for JSON trace dump
enco = lambda obj: (
    obj.isoformat()
    if isinstance(obj, datetime.datetime)
    or isinstance(obj, datetime.date)
    else None
)

# entry call for AWS Lambda
def lambda_handler(event, context):
    
    # extract the message that Inspector sent via SNS
    message = event['Records'][0]['Sns']['Message']
    print(message)

    # get inspector notification type
    notificationType = json.loads(message)['event']
    print('Handler: Notification type: {0}'.format(notificationType))
  
    # call the correct parser
    if notificationType == 'ASSESSMENT_RUN_STARTED' and 'processStartedMessages' in os.environ:
        try:
            rv = started.parse(message)
        except:
            print('Handler: Parse STARTED message: Returns error')
            return 1
    elif notificationType == 'ASSESSMENT_RUN_COMPLETED' and 'processCompletedMessages' in os.environ:
        try:
            rv = completed.parse(message)
        except:
            print('Handler: Parse COMPLETED message: Returns error')
            return 1
    elif notificationType == 'FINDING_REPORTED' and 'processFindingMessages' in os.environ:
        try:
            rv = finding.parse(message)      
        except:
            print('Handler: Parse FINDING message: Returns error')
            return 1
    else:
        print('Handler: Skipping unhandled/unwanted notification type: {0}'.format(notificationType))
        return 1
    
    # no message to be sent
    if not rv:
        return 1
            
    # generate email address for subscription from environment variable if set
    if 'emailAddress' in os.environ:
        destEmailAddr = os.environ['emailAddress']
    else:
        destEmailAddr = 'null@example.com'
            
    print('Handler: Email subscription: {0}'.format(destEmailAddr))
    
    snsTopic = 'slack-delivery-' + rv['SlackChannel']
    print('Handler: SNS topic: {0}'.format(snsTopic))

    # create SNS topic if necessary
    response = sns.create_topic(Name = snsTopic)
    snsTopicArn = response['TopicArn']

    # check to see if the subscription already exists
    subscribed = False
    response = sns.list_subscriptions_by_topic(TopicArn = snsTopicArn)

    # iterate through subscriptions array in paginated list
    while True:
        for subscription in response['Subscriptions']:
            if (subscription['Endpoint'] == destEmailAddr):
                subscribed = True
                break
        
        if 'NextToken' not in response:
            break
        
        response = sns.list_subscriptions_by_topic(
            TopicArn = snsTopicArn,
            NextToken = response['NextToken']
            )
        
    # create subscription if necessary
    if ( subscribed == False ):
        response = sns.subscribe(
            TopicArn = snsTopicArn,
            Protocol = 'email',
            Endpoint = destEmailAddr
            )

    # publish notification to topic
    response = sns.publish(
        TopicArn = snsTopicArn,
        Message = rv['MessageBody'],
        Subject = rv['Subject']
        )

    return 0