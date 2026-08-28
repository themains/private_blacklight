import scrapy
import json
import pandas as pd
import os
import requests
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
        test_websites = pd.read_csv("../../data/yg_ind_domain.csv")[["private_domain"]].drop_duplicates()
        test_websites = test_websites["private_domain"].tolist()

        # Ensure output folder exists
        os.makedirs(self.output_folder, exist_ok=True)

        for index, tw in enumerate(test_websites):
            print(index)
            print(f"Attempting to scrape: {tw}")
            
            http_url = "http://" + tw
            https_url = "https://" + tw

            # Check if the website is reachable
            if not self.is_website_reachable(http_url) and not self.is_website_reachable(https_url):
                self.logger.warning(f"Website unreachable: {tw}. Skipping...")
                self.log_error(f"Website unreachable: {tw}. Skipping...")
                continue

            url = https_url if self.is_website_reachable(https_url) else http_url
            print(f"Attempting to scrape: {url}")
            data = {"inUrl": url}

            yield scrapy.Request(
                url=blacklight_endpoint,
                method="POST",
                body=json.dumps(data),
                headers={'Content-Type': 'application/json'},
                meta={"website": tw, "retry_count": 0},  # Pass website name and retry count
                callback=self.parse,
                errback=self.handle_error  # Custom error handling
            )

    def parse(self, response):
        website = response.meta["website"]
        retry_count = response.meta["retry_count"]

        output_file = os.path.join(self.output_folder, f"{website.replace('.', '_')}.json")

        # Skip if the file already exists
        if os.path.exists(output_file):
            self.logger.info(f"Skipping {website}... File already exists.")
            return

        try:
            # Attempt to decode the JSON response
            json_data = json.loads(response.body)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to decode JSON for {website}.")
            self.log_error(f"Failed to decode JSON for {website}.")
            return

        # Check if 'groups' exists and is not empty
        groups = json_data.get("groups", [])
        if not groups:
            if retry_count < 3:
                self.logger.warning(f"'groups' key is missing or empty for {website}. Retrying ({retry_count + 1}/3)...")
                self.log_error(f"'groups' key is missing or empty for {website}. Retrying ({retry_count + 1}/3)...")
                yield scrapy.Request(
                    url=response.url,
                    method="POST",
                    body=response.request.body,
                    headers=response.request.headers,
                    meta={"website": website, "retry_count": retry_count + 1},
                    callback=self.parse,
                    errback=self.handle_error
                )
            else:
                self.logger.error(f"'groups' key is missing or empty for {website}. Max retries reached. Skipping...")
                self.log_error(f"'groups' key is missing or empty for {website}. Max retries reached. Skipping...")
            return

        # Save the raw JSON only if it is valid
        try:
            with open(output_file, "w") as f:
                json.dump(json_data, f, indent=4)
            self.logger.info(f"Saved data for {website} to {output_file}")
        except Exception as e:
            self.logger.error(f"Failed to save data for {website}: {e}")
            self.log_error(f"Failed to save data for {website}: {e}")
            return

        # Process 'cards' from the 'groups'
        cards = []
        for group in groups:
            cards.extend(group.get("cards", []))

        if not cards:
            self.logger.warning(f"No cards found in 'groups' for {website}.")
            self.log_error(f"No cards found in 'groups' for {website}. Skipping further processing...")
            return

        # Process each card
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

    def handle_error(self, failure):
        """Handle failed requests."""
        website = failure.request.meta["website"]
        self.logger.error(f"Request failed for {website}: {failure.value}")
        self.log_error(f"Request failed for {website}: {failure.value}")

    def is_website_reachable(self, url):
        """Check if a website is reachable with a HEAD or GET request, handling redirects."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            # Try HEAD request first for efficiency
            response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
            if response.status_code < 400:
                return True

            # Fallback to GET if HEAD doesn't provide a reliable response
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            return response.status_code < 400
        except requests.RequestException as e:
            self.logger.warning(f"Error checking website {url}: {e}")
            return False


    def log_error(self, message):
        """Log error messages to a dedicated log file."""
        with open(self.log_file, "a") as f:
            f.write(message + "\n")