import os
import json
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Output folder for JSON files
output_folder = "./website_trackers"
os.makedirs(output_folder, exist_ok=True)

# Base URL for WhoTracksMe
base_url = "https://www.ghostery.com/whotracksme/websites/"

# Function to scrape tracker data and statistics for a given website
def scrape_website_data(website):
    try:
        # Fetch the webpage
        url = f"{base_url}{website}"
        response = requests.get(url)
        response.raise_for_status()

        # Parse the HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Initialize the result dictionary
        result = {
            "website": website,
            "trackers": [],
            "statistics": {}
        }

        # Extract tracker information
        tracker_section = soup.find("div", class_="ds-wtm-entities cards")
        if tracker_section:
            tracker_entries = tracker_section.find_all("a", href=True)
            for entry in tracker_entries:
                tracker_name = entry.find("div", class_="ds-body-m ds-color-white ds-text-ellipsis")
                tracker_meta = entry.find("div", class_="ds-color-gray-400 ds-uppercase ds-label-xs ds-text-ellipsis")

                if tracker_name and tracker_meta:
                    tracker_name = tracker_name.text.strip()
                    meta_parts = [part.strip() for part in tracker_meta.text.split("•")]
                    percentage = meta_parts[0] if len(meta_parts) > 0 else "N/A"
                    company = meta_parts[1] if len(meta_parts) > 1 else "N/A"
                    category = meta_parts[2] if len(meta_parts) > 2 else "N/A"

                    result["trackers"].append({
                        "tracker": tracker_name,
                        "percentage": percentage,
                        "company": company,
                        "category": category
                    })

        # Extract additional statistics
        stats_section = soup.find_all("div", class_="ds-column ds-wtm-section-card medium")
        if stats_section:
            for stat in stats_section:
                stat_title = stat.find("p", class_="ds-display-2xs ds-color-gray-300")
                stat_value = stat.find("p", class_="ds-display-2xl")

                if stat_title and stat_value:
                    title = stat_title.text.strip()
                    value = stat_value.text.strip()
                    result["statistics"][title] = value

        return result

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {website}: {e}")
        return None

# List of websites to scrape
websites = pd.read_csv("yg_ind_domain.csv")["private_domain"]

# Iterate over websites and save JSON files
for website in websites:
    print(f"Scraping data for {website}...")
    data = scrape_website_data(website)

    if data:
        # Save to JSON file
        output_file = os.path.join(output_folder, f"{website.replace('.', '_')}_data.json")
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved data for {website} to {output_file}.")
    else:
        print(f"No data found for {website}.")

print("Scraping complete!")