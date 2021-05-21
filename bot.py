# import packages needed for this project
import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
import string
from datetime import datetime, timedelta

# load environment variable path and file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# configure flask app
app = Flask(__name__)

# add slackeventsadapter to handle events and endpoint for event requests
slack_event_adapter = SlackEventAdapter(os.environ['SIGNING_SECRET'], '/slack/events', app)

# create webclient with slack token
client = slack.WebClient(token=os.environ['SLACK_TOKEN'])

# return ID of the bot
BOT_ID = client.api_call("auth.test")['user_id']

# count messages of user
message_counts = {'user_id': 0}
welcome_messages = {}

BAD_WORDS = ['shit', 'fuck', 'cunt', 'whatever']


# welcome message that bot sends to new users in channel
class WelcomeMessage:
    START_TEXT = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': (
                'Welcome to this channel! \n\n'
                '*Get started by completing the tasks!*'
            )
        }
    }
    DIVIDER = {'type': 'divider'}

    def __init__(self, channel, user):
        self.channel = channel
        self.user = user
        self.icon_emoji = ':robot_face:'
        self.timestamp = ''
        self.completed = False

    def get_message(self):
        return {
            'ts': self.timestamp,
            'channel': self.channel,
            'username': 'Welcome Robot!',
            'icon_emoji': self.icon_emoji,
            'blocks': [
                self.START_TEXT,
                self.DIVIDER,
                self._get_reaction_task()
            ]
        }

    # method to change the emoji in the welcome message when a reaction is used
    def _get_reaction_task(self):
        checkmark = ':white_check_mark:'
        if not self.completed:
            checkmark = ':white_large_square:'
        text = f'{checkmark} *React to this message!*'
        return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': text}}


# function to send welcome message
def send_welcome_message(channel, user):
    if channel not in welcome_messages:
        welcome_messages[channel] = {}

    # if the user is already in the channel return (do not send welcome message)
    if user in welcome_messages[channel]:
        return

    welcome = WelcomeMessage(channel, user)
    message = welcome.get_message()
    response = client.chat_postMessage(**message)
    welcome.timestamp = response['ts']

    welcome_messages[channel][user] = welcome


def check_if_bad_words(message):
    msg = message.lower()
    msg = msg.translate(str.maketrans('', '', string.punctuation))

    return any(word in msg for word in BAD_WORDS)


# function to handle message events
@slack_event_adapter.on('message')
def message(payload):
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')

    # count messages for message_count slash command
    if user_id is not None and BOT_ID != user_id:
        if user_id in message_counts:
            message_counts[user_id] += 1
        else:
            message_counts[user_id] = 1

        # send welcome message to user's dm and check whether there are bad words in user's message
        if text.lower() == 'start':
            send_welcome_message(f'@{user_id}', user_id)
        elif check_if_bad_words(text):
            ts = event.get('ts')
            client.chat_postMessage(channel=channel_id, thread_ts=ts, text='that is a bad word')

        # client.chat_postMessage(channel=channel_id, text=text)


# create event to change welcome message when it is reacted to
@slack_event_adapter.on('reaction_added')
def reaction(payload):
    event = payload.get('event', {})
    channel_id = event.get('item', {}).get('channel')
    user_id = event.get('user')

    # check whether reaction is in the same channel as the welcome message
    if f'@{user_id}' not in welcome_messages:
        return

    welcome = welcome_messages[f'@{user_id}'][user_id]
    welcome.completed = True
    welcome.channel = channel_id
    message = welcome.get_message()
    updated_message = client.chat_update(**message)
    welcome.timestamp = updated_message['ts']


# create endpoint for slash command and return response
@app.route('/message-count', methods=['POST'])
def message_count():
    data = request.form
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    message_count = message_counts.get(user_id, 0)
    client.chat_postMessage(channel=channel_id, text=f'Messages: {message_count}')
    return Response(), 200


# Run flask app on default port and update on save
if __name__ == "__main__":
    app.run(debug=True)
