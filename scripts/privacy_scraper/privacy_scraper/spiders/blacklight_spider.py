import scrapy
import json
import pandas as pd
from scrapy.loader import ItemLoader
from privacy_scraper.items import PrivacyScraperItem

class BlacklightSpider(scrapy.Spider):
    name = "blacklight_spider"

    def start_requests(self):
        blacklight_endpoint = 'https://blacklight.api.themarkup.org'

        top_1k_test_df = pd.read_csv("data/alexa_top_1m/top_1k_alexa_sites.csv", header=None)
        test_websites = top_1k_test_df[0].to_list()

        for index, tw in enumerate(test_websites):
            print(index)
            print("attempting to scrape: {}".format(tw))
            url = "http://" + tw
            data = { "inUrl": url }
            yield scrapy.Request(url=blacklight_endpoint, method="POST", body=json.dumps(data), headers={'Content-Type':'application/json'}, callback=self.parse)

    def parse(self, response):

        json_data = json.loads(response.body)
        # import pdb; pdb.set_trace()

        try:
            uri_ins = json_data["uri_ins"]
            cards_1 = json_data["groups"][0]["cards"]
            cards_2 = json_data["groups"][1]["cards"]
            cards = cards_1 + cards_2
        except:
            print("request failed")
            return
        
        for card in cards:
            loader = ItemLoader(item=PrivacyScraperItem(), selector=card)
            loader.add_value("blacklight_json", json_data)
            loader.add_value("uri_ins", uri_ins)
            loader.add_value("cardType", card["cardType"])

            try:
                loader.add_value("testEventsFound", card["testEventsFound"])
            except:
                loader.add_value("testEventsFound", False)

            try:
                loader.add_value("bigNumber", card["bigNumber"])
            except:
                loader.add_value("bigNumber", 0)
            
            try:
                loader.add_value("onAvgStatement", card["onAvgStatement"])
            except:
                loader.add_value("onAvgStatement", "")
            
            try:
                loader.add_value("card_title", card["title"])
            except:
                loader.add_value("card_title", "")

            try:
                loader.add_value("bl_data_type", card["bl_data_type"])
            except:
                loader.add_value("bl_data_type", "")

            try:
                loader.add_value("ddg_company_lookup", card["ddg_company_lookup"])
            except:
                loader.add_value("ddg_company_lookup", "")
            
            try:
                loader.add_value("domains_found", card["domains_found"])
            except:
                loader.add_value("domains_found", "")

            try:
                loader.add_value("privacy_policy", card["privacy_policy"])
            except:
                loader.add_value("privacy_policy", "")

            try:
                loader.add_value("last_updated", card["last_updated"])
            except:
                loader.add_value("last_updated", "")

            # import pdb; pdb.set_trace()
            yield loader.load_item()