import json
import requests
import pandas as pd

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



top_1k_test_df = pd.read_csv("data/alexa_top_1m/top_1k_alexa_sites.csv", header=None)

test_websites = top_1k_test_df[0].to_list()

for index, tw in enumerate(test_websites):

    print(index)
    print(tw)
    test_file_path = "data/blacklight_data/top_1k_test.json"
    url = "http://" + tw
    blacklight_json_data = get_blacklight_privacy_data(url)
    write_json_to_file(blacklight_json_data, test_file_path)