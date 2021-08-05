import json
import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, Response, jsonify
import requests
from slackeventsapi import SlackEventAdapter


env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)

slack_event_adapter = SlackEventAdapter(os.environ['SIGNING_SECRET'], '/slack/events', app)
client = slack.WebClient(token=os.environ['SLACK_TOKEN'])

BOT_ID = client.api_call('auth.test')['user_id']
FEEDBACK_REQUEST = 'I want you to know I\'m not perfect, I\'m still learning too. Please help me improve by reacting to ' \
                   'the feedback I gave using one of the following emojis: :+1: :-1:  and replying to ' \
                   'my message with your thoughts about my feedback!'

intro_messages = {}
full_feedback = []
full_feedback_str = ''


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
                'To get feedback from me, use the \'/bot-feeback\' slash command followed by the message you want '
                'feedback on. \n'
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
                self.DIVIDER

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


# TODO: save user message and user feedback to txt file before setting up db
# TODO: save message that is sent for feedback into variable to be sent to api
def save_user_message(user_message):
    user_message_data = open('user_messages.txt', 'a')
    user_message_data.write(user_message)
    user_message_data.write('\n')
    user_message_data.close()


def get_api_feedback(user_message):
    global full_feedback
    msg = user_message
    result = requests.put('https://6apsi3nlz8.execute-api.eu-west-2.amazonaws.com/prod/user_input', data={'data': msg})\
        .json()
    json_string = json.dumps(result, indent=4, sort_keys=True)

    # TODO: extract bot feedback from API response and send to user via slack bot
    feedback = json.loads(json_string)
    for i in feedback:
        for key in feedback[i]:
            if 'sentence' in key:
                for a in feedback[i][key]['r_l']:
                    full_feedback.append(a['r_str'])
        # print(full_feedback)


# TODO: format 'full_feedback' before print, it is still in the list format
def full_feedback_string(feedback):
    global full_feedback_str
    for elem in feedback:
        full_feedback_str += elem
        full_feedback_str += '\n'


def clear_feedback(feedback_list):
    global full_feedback_str
    feedback_list.clear()
    feedback_str_clear = ''
    full_feedback_str = feedback_str_clear


# TODO: use reaction.get method to find out which emoji was used to react to the feedback
def feedback_reaction():
    return


@slack_event_adapter.on('team_join')
def new_user_intro_message(payload):
    event = payload.get('event', {})
    user_id = event.get('user')

    send_intro_message(f'@{user_id}', user_id)


@slack_event_adapter.on('message')
def message(payload):
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')

    # send intro message to user
    if text.lower() == 'intro':
        send_intro_message(f'@{user_id}', user_id)
        # TODO: make sure only when the user types a message the bot responds, the bot should not respond to its own
        # messages in this instance!!

    elif user_id is not None and BOT_ID != user_id:
        ts = event.get('ts')
        save_user_message(text)
        get_api_feedback(text)
        full_feedback_string(full_feedback)
        client.chat_postMessage(channel=user_id, text=full_feedback_str)
        client.chat_postMessage(channel=user_id, text=FEEDBACK_REQUEST)
        clear_feedback(full_feedback)
        # reaction = client.reactions_get(channel=user_id, timestamp=ts)
        # print(reaction)


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
    return jsonify(response_type='ephemeral', text='Feedback sent')
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


if __name__ == "__main__":
    app.run(debug=True)
