# Parser for ASSESSMENT_RUN_COMPLETED AWS Inspector SNS messages
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
inspector = boto3.client('inspector')

def parse(message):    

    # extract run ARN
    runArn = json.loads(message)['run']

    # get run and extract detail
    response = inspector.describe_assessment_runs(assessmentRunArns = [ runArn ])
    print(response)

    # skip badly formatted messages    
    try:
        assessment = response['assessmentRuns'][0]
    except OSError as err:
        print('Parse: Started: OS error: {0}'.format(err))
    except:
        print('Parse: Started: Unexpected error:', sys.exc_info()[0])
        raise

    # get Slack channel from assesment run attributes
    ndict = next((l for l in assessment['userAttributesForFindings'] if l['key'] == 'slackChannel'), None)
    channel = ndict['value'] if ndict else None
    if not channel:
        print('Parse: Started: No Slack channel associated with this instance')
        return None
        
    print('Parse: Started: Slack channel: {0}'.format(channel))

     # get template reporting threshold from assesment run attributes
    ndict = next((l for l in assessment['userAttributesForFindings'] if l['key'] == 'reportingThreshold'), None)
    tempThreshold = ndict['value'] if ndict else None

    # get (optional) regional severity reporting threshold if no template threshold set
    # template threshold has priority over regional threshold
    if tempThreshold is None:
        print('Parse: Completed: Template reporting threshold is not set')
        if 'reportingThreshold' in os.environ:
            threshold = os.environ['reportingThreshold'] + ' (region setting)'
            print('Parse: Completed: Regional reporting threshold is set to {0}'.format(os.environ['reportingThreshold']))
        else:
            print('Parse: Completed: Regional reporting threshold is not set. Using default 0')
            threshold = '0 (region default)'
    else:
        threshold = tempThreshold + ' (template setting)'
        print('Parse: Completed: Template reporting threshold is set to {0}'.format(tempThreshold))

    # get other run information to send via email: template name, region, date and duration
    name = inspector.describe_assessment_templates(
        assessmentTemplateArns = [assessment['assessmentTemplateArn']]
        )['assessmentTemplates'][0]['name']
            
    region = assessment['arn'].split(':')[3]
    date = assessment['startedAt']
    duration = str(assessment['durationInSeconds'])   

    # Format for date output
    date_format='%d/%m/%Y %H:%M %Z'

    # compose subject and message body
    subject = 'AWS Inspector Run | Started | Template <{0}>'.format(name)
    print('Parse: Started: Message subject: {0}'.format(subject))
    
    # un-comment the following line to dump the entire assessment as raw json
    #messageBody = json.dumps(assessment, default=enco, indent=2)

    messageBody = 'Region: {0}\nStarted at: {1}\nRun time: {2} seconds\nReporting threshold: {3}'.format(
        region, 
        date.strftime(date_format), 
        duration,
        threshold
        )

    print('Parse: Started: Message body: {0}'.format(messageBody))
    
    rv = {'SlackChannel' : channel, 'Subject' : subject, 'MessageBody' : messageBody}
    return rv