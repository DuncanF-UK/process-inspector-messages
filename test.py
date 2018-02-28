# Test harness for local testing
#	1) loads SNS event from 'event.json'
#	2) Sets environment vars to force all messages through

from __future__ import print_function

import json
import os

import lambda_function

if __name__ == "__main__":
    file = open('event.json').read()
    event = json.loads(file)
    context = []

    os.environ['processStartedMessages'] = 'true'
    os.environ['processCompletedMessages'] = 'true'
    os.environ['processFindingMessages'] = 'true'
    os.environ['reportingThreshold'] = '0'
    #os.environ['emailAddress'] = 'a@b.com'

    lambda_function.lambda_handler(event, context)