import json

# data = json.load('data.json')

with open('data.json') as json_file:
    data = json.load(json_file)

# print(type(data))

for i in data:
    # print(data[i])
    for key in data[i]:
        # print(key)
        if 'sentence' in key:
            # print(key)
            # print(data[i][key]['r_l'])
            # print('\n ----------')
            for a in data[i][key]['r_l']:
                print(key)
                print(a)
                print(a['r_str'])
                print('\n ----------')