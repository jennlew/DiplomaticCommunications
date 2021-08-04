import json
import requests


full_feedback = []
full_feedback_str = ''


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
        print(full_feedback)


def full_feedback_string(feedback):
    global full_feedback_str
    for elem in feedback:
        full_feedback_str += elem
        full_feedback_str += '\n'
    print(full_feedback_str)


get_api_feedback("I hate you. You always do this to me. I feel you don’t listen to me and ignore me")
full_feedback_string(full_feedback)



# data = json.load('data.json')

# with open('data.json') as json_file:
#     data = json.load(json_file)
#
# # print(type(data))
#
# for i in data:
#     # print(data[i])
#     for key in data[i]:
#         # print(key)
#         if 'sentence' in key:
#             # print(key)
#             # print(data[i][key]['r_l'])
#             # print('\n ----------')
#             for a in data[i][key]['r_l']:
#                 print(key)
#                 print(a)
#                 print(a['r_str'])
#                 print('\n ----------')
