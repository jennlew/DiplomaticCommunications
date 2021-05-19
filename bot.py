# import packages needed for this project
import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask
from slackeventsapi import SlackEventAdapter

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


# function to handle message events
@slack_event_adapter.on('message')
def message(payload):
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')

    # post message in response to user message in slack
    if BOT_ID != user_id:
        client.chat_postMessage(channel=channel_id, text=text)


# Run flask app on default port and update on save
if __name__ == "__main__":
    app.run(debug=True)
