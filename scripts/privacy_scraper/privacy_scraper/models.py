from sqlalchemy import create_engine, Column, Table, ForeignKey, MetaData
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Integer, String, Date, DateTime, Float, Boolean, Text, JSON)
from scrapy.utils.project import get_project_settings

Base = declarative_base()


def db_connect():
    """
    Performs database connection using database settings from settings.py.
    Returns sqlalchemy engine instance
    """
    return create_engine(get_project_settings().get("CONNECTION_STRING"))


def create_table(engine):
    Base.metadata.create_all(engine)


class PrivacyScraper(Base):
    __tablename__ = "privacy_scraper"
    id = Column(Integer, primary_key=True)
    blacklight_json = Column('blacklight_json', JSON())
    uri_ins = Column('uri_ins', String())
    cardType = Column('cardType', String())
    testEventsFound = Column('testEventsFound', Boolean())
    bigNumber = Column('bigNumber', Integer())
    onAvgStatement = Column('onAvgStatement', Text())
    card_title = Column('card_title', String())
    bl_data_type = Column('bl_data_type', String())
    ddg_company_lookup = Column('ddg_company_lookup', String())
    domains_found = Column('domains_found', Text())
    privacy_policy = Column('privacy_policy', String())
    last_updated = Column('last_updated', String())






