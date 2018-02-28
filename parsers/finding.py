# Parser for FINDING AWS Inspector SNS messages
#   1) Render into human readable format
#   2) Return message subject, body and Slack channel for delivery

# generic imports
from __future__ import print_function
import boto3
import json
import datetime
import sys
import os

sns = boto3.client('sns')
ec2 = boto3.client('ec2')
inspector = boto3.client('inspector')

def parse(message):  
    
    # extract finding ARN
    findingArn = json.loads(message)['finding']

    # get finding and extract detail
    response = inspector.describe_findings(findingArns = [ findingArn ], locale='EN_US')
    print(response)

    # skip badly formatted messages   
    try:
        finding = response['findings'][0]
    except OSError as err:
        print('Parse: Finding: OS error: {0}'.format(err))
    except:
        print('Parse: Finding: Unexpected error:', sys.exc_info()[0])
        raise

    # get Slack channel from assesment finding attributes
    ndict = next((l for l in finding['userAttributes'] if l['key'] == 'slackChannel'), None)
    channel = ndict['value'] if ndict else None 
    if not channel:
        print('Parse: Finding: No Slack channel associated with this instance')
        return None

    print('Parse: Finding: Slack channel: {0}'.format(channel))
                
    # skip uninteresting findings
    title = finding['title']
    if title == 'Unsupported Operating System or Version':
        print('Parse: Finding: Skipping finding: {0}'.format(title))
        return None
        
    if title == 'No potential security issues found':
        print('Parse: Finding: Skipping finding: {0}'.format(title))
        return None
     
    # get numerical finding severity level
    # read more about levels here: https://aws.amazon.com/inspector/faqs/
    severity = int(finding['numericSeverity'])
    if (severity == 9):
        sevStr = 'CRITICAL'
    elif (severity == 6):
        sevStr = 'Warning'
    else: # low = 3, info = 0
        sevStr = 'Low/Info'

    # get template reporting theshold from assessment finding attributes
    ndict = next((l for l in finding['userAttributes'] if l['key'] == 'reportingThreshold'), None)
    tempThreshold = ndict['value'] if ndict else None

    # get (optional) regional severity reporting threshold if no template threshold set
    # template threshold has priority over regional threshold
    if tempThreshold is None:
        print('Parse: Finding: Template reporting threshold is not set')
        if 'reportingThreshold' in os.environ:
            threshold = int(os.environ['reportingThreshold'])
            print('Parse: Finding: Regional reporting threshold is set to {0}'.format(threshold))
        else:
            print('Parse: Finding: Regional reporting threshold is not set. Using default 0')
            threshold = 0
    else:
        threshold = int(tempThreshold)
        print('Parse: Finding: Template reporting threshold is set to {0}'.format(threshold))

    # skip any findings below reporting threshold  
    if severity < threshold:
        print('Parse: Finding: Skipping finding ({0}) below reporting threshold ({1})'.format(str(severity), str(threshold)))
        return None

    # get the instance friendly name from EC2 tag 'Name' if set
    instanceTags = ec2.describe_instances(
        InstanceIds = [finding['assetAttributes']['agentId']]
        )['Reservations'][0]['Instances'][0]['Tags']
    
    ndict = next((l for l in instanceTags if l['Key'] == 'Name'), None)
    instanceName = ndict['Value'] if ndict else None 

    # compose subject and message body
    if not instanceName:
        subject = 'AWS Inspector Finding | {} | Instance <no name>'.format(sevStr)
    else:
        subject = 'AWS Inspector Finding | {} | Instance <{}>'.format(sevStr, instanceName)

    print('Parse: Finding: Message subject: {0}'.format(subject))

    # un-comment the following line to dump the entire finding as raw json
    #messageBody = json.dumps(finding, default=enco, indent=2)

    messageBody = 'Title:\n{0}\n\nDescription:\n{1}\n\nRecommendation:\n{2}'.format(
        title, 
        finding['description'], 
        finding['recommendation']
        )
        
    print('Parse: Finding: Message body: {0}'.format(messageBody))
    
    rv = {'SlackChannel' : channel, 'Subject' : subject, 'MessageBody' : messageBody}
    return rv