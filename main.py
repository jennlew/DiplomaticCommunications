from dotenv import load_dotenv
from flask import Flask, request, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
import json
import slack
import os
from pathlib import Path
import requests
from slackeventsapi import SlackEventAdapter

# configure Flask app
app = Flask(__name__)

# load environment variable path and file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# specify whether it is a development or production environment
ENV = 'prod'

# get database url from environment variables
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

# change beginning of database url as the previous url is no longer supported by heroku
if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

# if running on the development environment use the local database and reload when changes are made to code
if ENV == 'dev':
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('POSTGRES_DEV_URL')
# if running on the production environment use the heroku database
else:
    # app.debug = False
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI

# configure database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# create database table
class MessageFeedback(db.Model):
    __tablename__ = 'message_and_feedback'
    id = db.Column(db.Integer, primary_key=True)
    user_message = db.Column(db.String(250))
    bot_feedback = db.Column(db.String(250))

    def __init__(self, user_message, bot_feedback):
        self.user_message = user_message
        self.bot_feedback = bot_feedback


# add slackeventsadapter to handle events and endpoint for event requests
slack_event_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'], '/slack/events', app)
# create webclient with slack token
client = slack.WebClient(token=os.environ['SLACK_TOKEN'])

# return ID of the bot
BOT_ID = client.api_call('auth.test')['user_id']
FEEDBACK_REQUEST = 'I want you to know I\'m not perfect, I\'m still learning too. Please help me improve by reacting ' \
                   'to the feedback I gave using one of the following emojis: :+1: :-1:  and replying to ' \
                   'my message with your thoughts about my feedback!'

intro_messages = {}
full_feedback = []
full_feedback_str = ''


# introduction message that bot sends to new users in channel
class IntroMessage:
    START_TEXT = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': (
                'Hi, I\'m Sempi.\n \n'
                'I alert you to language that may sound judgmental or triggering. When people are triggered, they\'ll become less likely to hear you and respond in a way you\'d like. I\'ll help you stick to objective facts so you can convey your message more effectively. I\'ll also give suggestions for ways you can make your message more powerful and clear. \n \n '
                'To get feedback from me, use the \'/bot-feedback\' slash command followed by the message you want feedback on. \n \n'
                'How to exempt phrases from feedback: \n'
                'If you want to exempt something from my feedback, you can write it in curly brackets. For example, imagine you wrote, "He is elderly" and I give the feedback that "\'elderly\' seems to be a protected characteristic." But perhaps use of the phrase "elderly" is appropriate for your context and you want to exempt the phrase from my analysis. To exempt this phrase, you would write, "He is {elderly}." and I will exempt everything inside the curly brackets from my comments.'
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
                self.DIVIDER

            ]
        }


# function to send intro message
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


# save user message to txt file
def save_user_message(user_message):
    user_message_data = open('user_messages.txt', 'a')
    user_message_data.write(user_message)
    user_message_data.write('\n')
    user_message_data.close()


# send user message to api and receive feedback
def get_api_feedback(user_message):
    global full_feedback
    msg = user_message
    result = requests.put('https://6apsi3nlz8.execute-api.eu-west-2.amazonaws.com/prod/user_input', data={'data': msg})\
        .json()
    json_string = json.dumps(result, indent=4, sort_keys=True)

    # extract bot feedback from API json response
    feedback = json.loads(json_string)
    for i in feedback:
        for key in feedback[i]:
            if 'sentence' in key:
                for a in feedback[i][key]['r_l']:
                    full_feedback.append(a['r_str'])


# format feedback before sending - change from list to string
def full_feedback_string(feedback):
    global full_feedback_str
    for elem in feedback:
        full_feedback_str += elem
        full_feedback_str += '\n'


# clear feedback list
def clear_feedback(feedback_list):
    global full_feedback_str
    feedback_list.clear()
    feedback_str_clear = ''
    full_feedback_str = feedback_str_clear


# function to handle team joining events
@slack_event_adapter.on('team_join')
def new_user_intro_message(payload):
    event = payload.get('event', {})
    user_id = event.get('user')

    # send the intro message when a new member joins the team
    send_intro_message(f'@{user_id}', user_id)


# function to handle message events
@slack_event_adapter.on('message')
def message(payload):
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')

    # send intro message to user when they type intro (for demo purposes)
    if text.lower() == 'intro':
        send_intro_message(f'@{user_id}', user_id)

    # check the message did not come from the bot, then send feedback
    elif user_id is not None and BOT_ID != user_id:
        ts = event.get('ts')
        save_user_message(text)
        get_api_feedback(text)
        full_feedback_string(full_feedback)
        client.chat_postMessage(channel=user_id, text=full_feedback_str)
        client.chat_postMessage(channel=user_id, text=FEEDBACK_REQUEST)
        clear_feedback(full_feedback)
    if channel_id == user_id:
        client.chat_postMessage(channel=user_id, text='a message was posted in this dm channel')
        print('dm sent!!')

# function to handle reaction events
@slack_event_adapter.on('reaction_added')
def feedback_reaction(payload):
    event = payload.get('event', {})
    user_id = event.get('user')
    reaction = event.get('reaction')
    type = event.get('item', {}).get('message')
    item_user = event.get('item_user')

    # check whether the message was sent by the bot
    if item_user == BOT_ID and type == 'message':
        if reaction == 'thumbsup':
            # save to good column next to feedback message
            print(reaction)
        elif reaction == 'thumbsdown':
            # save to bad column
            print(reaction)
        else:
            print('different emoji')


# detect whether bot-feedback slash command was used
@app.route('/bot-feedback', methods=['POST'])
def bot_feedback_slash():
    data = request.form
    user_id = data.get('user')
    channel_id = data.get('channel_id')
    text = data.get('text')
    ts = data.get('ts')

    save_user_message(text)
    get_api_feedback(text)
    full_feedback_string(full_feedback)
    client.chat_postMessage(channel=channel_id, thread_ts=ts, text=full_feedback_str)
    client.chat_postMessage(channel=channel_id, text=FEEDBACK_REQUEST, thread_ts=ts)
    clear_feedback(full_feedback)

    # save user message and bot feedback to database
    db_data = MessageFeedback(user_message=text, bot_feedback=full_feedback_str)
    db.session.add(db_data)
    db.session.commit()
    return jsonify(response_type='ephemeral', text=f'Feedback sent for message \'{text}\'')
    # return Response(), 220


@app.route('/conversation-history', methods=['POST'])
def convo_history_slash():
    data = request.form
    user_id = data.get('user')
    channel_id = data.get('channel_id')
    text = data.get('text')
    ts = data.get('ts')

    client.conversations_history(channel=channel_id, inclusive=True, lastest='now')
    return


# Run flask app on default port and update on save
if __name__ == "__main__":
    app.run(debug=True)
