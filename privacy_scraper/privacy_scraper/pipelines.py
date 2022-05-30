# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from sqlalchemy.orm import sessionmaker
from scrapy.exceptions import DropItem
from privacy_scraper.models import PrivacyScraper, db_connect, create_table
import json

class DefaultValuesPipeline(object):
    def process_item(self, item, spider):
        for field in item.fields:
            item.setdefault(field, 'NULL')
        return item

class PrivacyScraperPipeline:
    def process_item(self, item, spider):
        return item

class SavePrivacyPipeline:
    def __init__(self):
        """
        Initializes database connection and sessionmaker
        Creates tables
        """
        engine = db_connect()
        create_table(engine)
        self.Session = sessionmaker(bind=engine)


    def process_item(self, item, spider):
        """Save privacy rows in the database
        This method is called for every item pipeline component
        """
        session = self.Session()
        privacy_scraper = PrivacyScraper()

        try:
            privacy_scraper.blacklight_json = json.dumps(item["blacklight_json"][0])
            privacy_scraper.uri_ins = item["uri_ins"][0]
            privacy_scraper.cardType = item["cardType"][0]
            privacy_scraper.testEventsFound = item["testEventsFound"][0]
            privacy_scraper.bigNumber = item["bigNumber"][0]
            privacy_scraper.onAvgStatement = item["onAvgStatement"][0]
            privacy_scraper.card_title = item["card_title"][0]
            privacy_scraper.bl_data_type = item["bl_data_type"][0]
            privacy_scraper.ddg_company_lookup = item["ddg_company_lookup"][0]
            privacy_scraper.domains_found = item["domains_found"][0]
            privacy_scraper.privacy_policy = item["privacy_policy"][0]
            privacy_scraper.last_updated = item["last_updated"][0]
        except:
            import pdb; pdb.set_trace()

        try:
            session.add(privacy_scraper)
            session.commit()
        except:
            session.rollback()
            raise

        finally:
            session.close()

        return item