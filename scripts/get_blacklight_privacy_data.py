import os
import json
import logging
import requests
import pandas as pd
from datetime import datetime

# Blacklight API endpoint
BLACKLIGHT_ENDPOINT = 'https://blacklight-us-ca.api.themarkup.org'

# Setup logging
LOG_FILE = "error_log.json"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "domain_name": "%(domain_name)s", "url": "%(url)s", "error_message": "%(error_message)s"}',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Function to get privacy data from Blacklight
def get_blacklight_privacy_data(url):
    try:
        data = {"inUrl": url}
        r = requests.post(url=BLACKLIGHT_ENDPOINT, json=data)
        r.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
        return r.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error fetching data for {url}: {e}")

# Function to save JSON data to a file
def write_json_to_file(json_data, file_path):
    with open(file_path, 'w') as json_file:
        json.dump(json_data, json_file, indent=2)

# Load and deduplicate websites
websites = pd.read_csv("yg_ind_domain.csv")[["private_domain"]].drop_duplicates()

# Limit to first 5 for testing (remove slicing for full processing)
websites = websites.head(5)

# Define the output folder
output_folder = "./blacklight_json"
os.makedirs(output_folder, exist_ok=True)  # Create the folder if it doesn't exist

# Iterate over websites and fetch Blacklight data
for idx, row in websites.iterrows():
    domain_name = row["private_domain"]
    url = f"http://{domain_name}"  # Ensure proper URL format

    # Define the output file path
    output_file = os.path.join(output_folder, f"{domain_name}.json")

    # Skip if the file already exists
    if os.path.exists(output_file):
        print(f"Skipping {domain_name}... (File already exists)")
        continue

    print(f"Fetching Blacklight data for {url}...")

    try:
        # Fetch the data
        blacklight_data = get_blacklight_privacy_data(url)

        # Add the domain name to the data for reference
        blacklight_data["domain_name"] = domain_name

        # Write to the JSON file
        write_json_to_file(blacklight_data, output_file)
        print(f"Saved data for {domain_name} to {output_file}")
    except Exception as e:
        # Log the error using logging
        logging.error(
            "An error occurred while fetching Blacklight data.",
            extra={
                "domain_name": domain_name,
                "url": url,
                "error_message": str(e)
            }
        )
        print(f"Logged error for {domain_name}")

print("Processing complete!")
