import math
import time
import urllib
import argparse
from datetime import datetime, timedelta

# --------------------------------------------------------------------------------
import pymongo
client = pymongo.MongoClient("localhost", 27017)
db = client.wechat 

class Database(object):
    DATETIME_MIN = datetime(2000, 1, 1)
    DATETIME_MAX = datetime(2100, 1, 1)

    def __init__(self, dbName):
        self._db = db[dbName]
        self._startDate = self.DATETIME_MIN
        self._endDate = self.DATETIME_MAX
        self._search = ''

# --------------------------------------------------------------------------------
class Object: 
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

# --------------------------------------------------------------------------------
DATE_FORMAT = "%Y-%m-%d"

def date2str(date):
    return date.strftime(DATE_FORMAT)

def str2date(string):
    return datetime.strptime(string, DATE_FORMAT)
