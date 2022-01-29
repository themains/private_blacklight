import json
import requests
import lxml.html
import pdb

# note: url must be in form {example.com}.html
def get_whotracksme_privacy_data(url):
    whotracksme_endpoint = 'https://whotracks.me/websites/{}'.format(url)

    response = requests.get(url=whotracksme_endpoint)
    whotracksme_data = parse_whotracksme_data(response)
    whotracksme_json_data = json.dumps(whotracksme_data)
    return whotracksme_json_data

def parse_whotracksme_data(response):
    whotracksme_data = {}
    trackers_list = []
    doc = lxml.html.fromstring(response.text)

    site = doc.xpath("//h1/a/text()")[0]
    size_of_user_data_from_trackers_per_page = doc.xpath("//p[@class='subtitle']/span/text()")[0].strip()
    avg_num_trackers_per_page = doc.xpath("//span[@class='header red-color']/text()")[0].strip()
    prop_page_loads_with_tracking = doc.xpath("//h3[contains(.,'PROPORTION OF TRAFFIC')]/following-sibling::div/text()")[0].strip()
    num_requests_to_trackers_per_page_load = doc.xpath("//h3[contains(.,'REQUESTS TO TRACKERS')]/following-sibling::div/text()")[0].strip()
    tracking_methods = doc.xpath("//p[@class='tracking-method']/span/text()")
    trackers = doc.xpath("//h3[contains(.,'Trackers Seen')]/following-sibling::div/descendant::div[@id='frequency']/ul/li")

    for tracker in trackers:
        tracker_name = tracker.xpath("a[@class='entity-name']/text()")[0].strip()
        tracker_percentage = tracker.xpath("span[@class='percentage']/text()")[0].strip()
        tracker_company = tracker.xpath("span[@class='percentage']/following-sibling::span/text()")[0].strip()
        tracker_desc_link = tracker.xpath("a[@class='entity-name']/@href")[0].strip()
        tracker_company = tracker.xpath("span[@class='percentage']/following-sibling::span/text()")[0].strip()

        trackers_list.append({
            'tracker_name': tracker_name,
            'tracker_percentage': tracker_percentage,
            'tracker_desc_link': tracker_desc_link,
            'tracker_company': tracker_company,
        })

    whotracksme_data["site"] = site
    whotracksme_data["size_of_user_data_from_trackers_per_page"] = size_of_user_data_from_trackers_per_page
    whotracksme_data["avg_num_trackers_per_page"] = avg_num_trackers_per_page
    whotracksme_data["prop_page_loads_with_tracking"] = prop_page_loads_with_tracking
    whotracksme_data["num_requests_to_trackers_per_page_load"] = num_requests_to_trackers_per_page_load
    whotracksme_data["tracking_methods"] = tracking_methods
    whotracksme_data["trackers"] = trackers_list

    return whotracksme_data



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
    test_file_path = "whotracksme_data/{}.json".format(tw)
    url = tw + ".html"
    whotracksme_json_data = get_whotracksme_privacy_data(url)
    write_json_to_file(whotracksme_json_data, test_file_path)