import json

import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, Response
import requests
from slackeventsapi import SlackEventAdapter
import string

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)

slack_event_adapter = SlackEventAdapter(os.environ['SIGNING_SECRET'], '/slack/events', app)
client = slack.WebClient(token=os.environ['SLACK_TOKEN'])

BOT_ID = client.api_call('auth.test')['user_id']

intro_messages = {}
result = ''


class IntroMessage:
    START_TEXT = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': (
                'Hi, I\'m Sempi.\n \n'
                'I alert you to language that may sound judgmental or triggering. When people are triggered, they\'ll '
                'become less likely to hear you and respond in a way you\'d like. I\'ll help you stick to objective '
                'facts so you can convey your message more effectively. I\'ll also give suggestions for ways you can '
                'make your message more powerful and clear. \n \n '
                'How to exempt phrases from feedback: \n'
                'If you want to exempt something from my feedback, you can write it in curly brackets. For example, '
                'imagine you wrote, "He is elderly" and I give the feedback that "\'elderly\' seems to be a protected '
                'characteristic." But perhaps use of the phrase "elderly" is appropriate for your context and you want '
                'to exempt the phrase from my analysis. To exempt this phrase, you would write, "He is {elderly}." and '
                'I will exempt everything inside the curly brackets from my comments.'
            )
        }
    }
    DIVIDER = {'type': 'divider'}

    def __init__(self, channel, user):
        self.channel = channel
        self.user = user
        self.timestamp = ''

    def get_message(self):
        return{
            'ts': self.timestamp,
            'channel': self.channel,
            'blocks': [
                self.START_TEXT,
                self.DIVIDER,

            ]
        }


def send_intro_message(channel, user):
    if channel not in intro_messages:
        intro_messages[channel] = {}

    if user in intro_messages[channel]:
        return

    intro = IntroMessage(channel, user)
    first_message = intro.get_message()
    response = client.chat_postMessage(**first_message)
    intro.timestamp = response['ts']

    intro_messages[channel][user] = intro


# TODO: save message that is sent for feedback into variable to be sent to api
def save_user_message(user_message):
    global result
    msg = user_message
    result = requests.put('https://6apsi3nlz8.execute-api.eu-west-2.amazonaws.com/prod/user_input', data={'data': msg})\
        .json()
    print(json.dumps(result, indent=4, sort_keys=True))


@slack_event_adapter.on('message')
def message(payload):
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')

    # send intro message to user
    if text.lower() == 'intro':
        send_intro_message(f'@{user_id}', user_id)
    elif save_user_message(text):
        client.chat_postMessage(channel=channel_id, text=result)

    # TODO: save user message and user feedback to txt file before setting up db


if __name__ == "__main__":
    app.run(debug=True)
