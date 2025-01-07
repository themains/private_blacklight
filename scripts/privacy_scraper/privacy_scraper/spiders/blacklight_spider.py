import scrapy
import json
import pandas as pd
import os
from scrapy.loader import ItemLoader
from privacy_scraper.items import PrivacyScraperItem

class BlacklightSpider(scrapy.Spider):
    name = "blacklight_spider"

    # Define the output folder to store JSON files
    output_folder = "./blacklight_json"
    log_file = "./blacklight_errors.log"

    def start_requests(self):
        blacklight_endpoint = 'https://blacklight-us-ca.api.themarkup.org'

        # Load the list of websites
        test_websites = pd.read_csv("../../data/yg_ind_domain.csv")[["private_domain"]].drop_duplicates()[3000:]
        test_websites = test_websites["private_domain"].tolist()  # Convert to a list

        # Ensure output folder exists
        os.makedirs(self.output_folder, exist_ok=True)

        for index, tw in enumerate(test_websites):
            print(index)
            print(f"Attempting to scrape: {tw}")
            url = "http://" + tw
            data = {"inUrl": url}
            yield scrapy.Request(
                url=blacklight_endpoint,
                method="POST",
                body=json.dumps(data),
                headers={'Content-Type': 'application/json'},
                meta={"website": tw},  # Pass the website name for saving
                callback=self.parse
            )

    def parse(self, response):
        # Extract the website from meta
        website = response.meta["website"]

        # Define the output file path
        output_file = os.path.join(self.output_folder, f"{website.replace('.', '_')}.json")

        # Check if the file already exists
        if os.path.exists(output_file):
            self.log(f"Skipping {website}... File already exists.")
            return

        # Attempt to decode JSON response
        try:
            json_data = json.loads(response.body)
        except json.JSONDecodeError:
            self.log(f"Failed to decode JSON for {website}.", level=scrapy.log.ERROR)
            self.log_error(f"Failed to decode JSON for {website}.")
            return

        # Save the JSON response to a file
        try:
            with open(output_file, "w") as f:
                json.dump(json_data, f, indent=4)
            self.log(f"Saved data for {website} to {output_file}")
        except Exception as e:
            self.log(f"Failed to save data for {website}: {e}", level=scrapy.log.ERROR)
            self.log_error(f"Failed to save data for {website}: {e}")
            return

        # Process cards in the response
        try:
            cards_1 = json_data["groups"][0]["cards"]
            cards_2 = json_data["groups"][1]["cards"]
            cards = cards_1 + cards_2
        except KeyError as e:
            self.log(f"Missing keys in JSON for {website}: {e}", level=scrapy.log.ERROR)
            self.log_error(f"Missing keys in JSON for {website}: {e}")
            return

        for card in cards:
            loader = ItemLoader(item=PrivacyScraperItem(), selector=card)
            loader.add_value("blacklight_json", json_data)
            loader.add_value("uri_ins", json_data.get("uri_ins", ""))
            loader.add_value("cardType", card.get("cardType", ""))

            loader.add_value("testEventsFound", card.get("testEventsFound", False))
            loader.add_value("bigNumber", card.get("bigNumber", 0))
            loader.add_value("onAvgStatement", card.get("onAvgStatement", ""))
            loader.add_value("card_title", card.get("title", ""))
            loader.add_value("bl_data_type", card.get("bl_data_type", ""))
            loader.add_value("ddg_company_lookup", card.get("ddg_company_lookup", ""))
            loader.add_value("domains_found", card.get("domains_found", ""))
            loader.add_value("privacy_policy", card.get("privacy_policy", ""))
            loader.add_value("last_updated", card.get("last_updated", ""))

            yield loader.load_item()

    def log_error(self, message):
        """Log error messages to a dedicated log file."""
        with open(self.log_file, "a") as f:
            f.write(message + "\n")
