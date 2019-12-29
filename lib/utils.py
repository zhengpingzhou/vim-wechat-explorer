import math
import time
import urllib
import argparse
from datetime import datetime, timedelta

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