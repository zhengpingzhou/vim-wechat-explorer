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
    try: date = datetime.strptime(string, DATE_FORMAT)
    except: 
        try: date = datetime.strptime(string, "%Y-%m")
        except: date = datetime.strptime(string, "%Y")
    return date