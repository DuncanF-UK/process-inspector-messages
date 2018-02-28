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
        print('Parse: Completed: OS error: {0}'.format(err))
    except:
        print('Parse: Completed: unexpected error:', sys.exc_info()[0])
        raise

    # get Slack channel from assesment run attributes
    ndict = next((l for l in assessment['userAttributesForFindings'] if l['key'] == 'slackChannel'), None)
    channel = ndict['value'] if ndict else None
    if not channel:
        print('Parse: Completed: No Slack channel associated with this instance')
        return None
        
    print('Parse: Completed: Slack channel: {0}'.format(channel))
 
     # get template reporting threshold from assesment run attributes
    ndict = next((l for l in assessment['userAttributesForFindings'] if l['key'] == 'reportingThreshold'), None)
    tempThreshold = ndict['value'] if ndict else None

    # get (optional) regional severity reporting threshold if no template threshold set
    # template threshold has priority over regional threshold
    if tempThreshold is None:
        print('Parse: Completed: Template reporting threshold is not set')
        if 'reportingThreshold' in os.environ:
            threshold = int(os.environ['reportingThreshold'])
            print('Parse: Completed: Regional reporting threshold is set to {0}'.format(threshold))
        else:
            print('Parse: Completed: Regional reporting threshold is not set. Using default 0')
            threshold = 0
    else:
        threshold = int(tempThreshold)
        print('Parse: Completed: Template reporting threshold is set to {0}'.format(threshold))

    # get other run information to send via email: template name, region, date and finding count
    name = inspector.describe_assessment_templates(
        assessmentTemplateArns = [assessment['assessmentTemplateArn']]
        )['assessmentTemplates'][0]['name']
            
    region = assessment['arn'].split(':')[3]
    date = assessment['completedAt']
    counts = assessment['findingCounts']

    # Format for date output
    date_format='%d/%m/%Y %H:%M %Z'
    
    # compose subject and message body
    subject = 'AWS Inspector Run | Complete | Template <{0}>'.format(name)
    print('Parse: Completed: Message subject: {0}'.format(subject))
    
    # un-comment the following line to dump the entire assessment as raw json
    #messageBody = json.dumps(assessment, default=enco, indent=2)

    messageBody = 'Region: {0}\nCompleted at: {1}\nFindings: High ({2}) | Medium ({3}) | Low ({4}) | Info ({5})'.format(
        region, 
        date.strftime(date_format),
        str(counts['High']), 
        str(counts['Medium']),
        str(counts['Low']), 
        str(counts['Informational'])
        )

    print('Parse: Completed: Message body: {0}'.format(messageBody))

    # warn user of messages that are unreported in the Slack channel due to a reporting threshold.
    # In AWS speak findings have a numeric severity between 0 and 10. AWS maps these to categories thus:
    # high:9, medium:6, low:3 and informational:0

    omitted = 0
    if threshold > 9:
        omitted += counts['High']

    if threshold > 6:
        omitted += counts['Medium']

    if threshold > 3:
        omitted += counts['Low']

    if threshold > 0:
        omitted += counts['Informational']
        messageBody += '\nWarning: {0} findings omitted in channel (reporting threshold is {1})'.format(
            omitted,
            threshold
            )

    rv = {'SlackChannel' : channel, 'Subject' : subject, 'MessageBody' : messageBody}
    return rv