# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class PrivacyScraperItem(scrapy.Item):
    # define the fields for your item here like:
    blacklight_json = scrapy.Field()
    uri_ins = scrapy.Field()
    cardType = scrapy.Field()
    testEventsFound = scrapy.Field()
    bigNumber = scrapy.Field()
    onAvgStatement = scrapy.Field()
    card_title = scrapy.Field()
    bl_data_type = scrapy.Field()
    ddg_company_lookup = scrapy.Field()
    domains_found = scrapy.Field()
    privacy_policy = scrapy.Field()
    last_updated = scrapy.Field()

