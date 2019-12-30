import math
import time
import urllib
import argparse
from datetime import datetime, timedelta

from lib.utils import Object
from lib.utils import date2str, str2date

import pymongo
client = pymongo.MongoClient("localhost", 27017)
db = client.wechat 


def preprocessMsg(args, msgDict):
    msg = Object(**msgDict)
    msg.content = msg.content.replace('??', '[emoji]')
    if msg.sender == '我':
        msg.profile = args.myProfile
        msg.senderName = args.myName if args.myName else msg.sender
    else:
        msg.profile = args.yourProfile
        msg.senderName = args.yourName if args.yourName else msg.sender
    return msg


class Database(object):
    DATETIME_MIN = datetime(2000, 1, 1)
    DATETIME_MAX = datetime(2100, 1, 1)
    SEC_INTERVAL = 1800     # 30min
    MSG_INTERVAL = 180      # 3min

    def __init__(self, args, dbName, useCache=False):
        self._db = db[dbName]
        self._startDate = self.DATETIME_MIN
        self._endDate = self.DATETIME_MAX
        self._search = ''
        self._cache = dict()
        self._useCache = useCache
        self._date = None
        self.args = args

    @property
    def date(self):
        return date2str(self._date) if self._date else ''
    

    def insertMany(self, msgList):
        nAdd = 0
        for msg in msgList:
            try: self._db.insert_one(vars(msg)); nAdd += 1
            except: print('Add failed! msgIdx:', msg.idx)  
        print('nAdd:', nAdd)

    
    def deleteMany(self, msgList):
        nDel = 0
        for msg in msgList:
            try: nDel += self._db.delete_one({'datetime': msg.datetime}).deleted_count
            except: print('Del failed! msgIdx:', msg.idx)  
        print('nDel:', nDel)

    
    def find(self, sql):
        found = self._db.find(sql)
        found = sorted(found, key=lambda msg: msg['idx'], reverse=True)
        return found


    def queryDate(self, date):
        self._date = date = str2date(date) if type(date) == str else date
        sql = {'datetime': {'$lt': date + timedelta(days=1), '$gte': date}}
        found = self.find(sql)
        return Object(msgList = found)


    def query(self, preprocess, **kwargs):
        if 'startDate' in kwargs:
            self._startDate = str2date(kwargs['startDate'])
        if 'endDate' in kwargs:
            self._endDate = str2date(kwargs['endDate'])
        if 'search' in kwargs:
            self._search = kwargs['search'].strip()

        sql = {'datetime': {'$lte': self._endDate, '$gte': self._startDate}}
        if self._search != '': sql['content'] = {'$regex': '.*' + self._search + '.*'}

        cacheKey = (self._startDate, self._endDate)
        if self._useCache and preprocess and self._search == '' and cacheKey in self._cache:
            print('Using cache...')
            return self._cache[cacheKey]

        found = self.find(sql)
        result = self.preprocess(found) if preprocess else Object(msgList=found)

        if self._useCache and preprocess and self._search == '': 
            print('Storing cache...')
            self._cache[cacheKey] = result

        return result


    def preprocess(self, found):     
        result = Object(
            secList = [],
            msg2sec = {0: 1},
            msg2parent = {0: 0},
            startDate = self._startDate,
            endDate = self._endDate,
            search = self._search)      
        if not found: return result

        secIdx = 1
        msgList = []
        lastDate = found[0]['datetime']
        dummy = {'datetime': self.DATETIME_MAX, 'sender': '', 'content': '', 'idx': -1}

        for msg in found + [dummy]:
            msg = preprocessMsg(self.args, msg)

            if (msg.datetime - lastDate).seconds > self.SEC_INTERVAL:
                sec = Object(
                    msgList = msgList, 
                    id = 'sec' + str(secIdx), 
                    idx = secIdx)
                if msgList: result.secList.append(sec)
                msgList = []

            secIdx = len(result.secList) + 1
            result.msg2sec[msg.idx] = secIdx

            if len(msgList) > 0 and msgList[-1].sender == msg.sender and (msg.datetime - lastDate).seconds < self.MSG_INTERVAL:
                msgList[-1].content += '\n' + msg.content
                result.msg2parent[msg.idx] = msgList[-1].idx
            else:
                msgList.append(msg)
                result.msg2parent[msg.idx] = msg.idx

            lastDate = msg.datetime

        return result
