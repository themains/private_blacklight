import json
import requests

# note: url must be in form http://{example.com}
def get_blacklight_privacy_data(url):
    blacklight_endpoint = 'https://blacklight.api.themarkup.org'
    data = { "inUrl": url }

    r = requests.post(url=blacklight_endpoint, json=data)
    result = r.json()
    return result

def write_json_to_file(json_data, file_path):
    with open(file_path, 'a+') as json_file:
        json.dump(json_data, json_file)


test_websites = [
    'google.com',
    'facebook.com',
    'twitter.com',
    'nytimes.com',
    'foxnews.com'
]

for tw in test_websites:
    test_file_path = "blacklight_data/{}.json".format(tw)
    url = "http://" + tw
    blacklight_json_data = get_blacklight_privacy_data(url)
    write_json_to_file(blacklight_json_data, test_file_path)