import math
import time
import urllib
import argparse
from datetime import datetime, timedelta

import pymongo
from easydict import EasyDict as edict

from flask import Flask, request, render_template, redirect

parser = argparse.ArgumentParser()
parser.add_argument('--my-name', type=str, default='')
parser.add_argument('--your-name', type=str, default='')
parser.add_argument('--my-profile', type=str, default='me.png', help='filename of customized profile. must be under static/img/.')
parser.add_argument('--your-profile', type=str, default='you.png', help='filename of customized profile. must be under static/img/.')
parser.add_argument('--start-date', type=str, default='2000-01-01')
parser.add_argument('--end-date', type=str, default='2100-01-01')
parser.add_argument('--hide-control', action='store_true', help='set to hide control panel on default.')
args = parser.parse_args()

client = pymongo.MongoClient("localhost", 27017)
db = client.wechat 
partner = db.partner 

DATE_FORMAT = "%Y-%m-%d"
params = edict(
    startDate=datetime.strptime(args.start_date, DATE_FORMAT),
    endDate=datetime.strptime(args.end_date, DATE_FORMAT),
    search=''
)

status = edict(
    curPage = 1,
    startPage = 1,
    endPage = 6,
    pages = [1, 2, 3, 4, 5, 6],
    maxPage = 100,
    nPageVisible = 6,
    nSessVisible = 10,
    startSess = 1,
    endSess = 10,
    startSessId = 'sec1',
    endSessId = 'sec10',
    sess_list = None
)

cache = dict()

app = Flask(__name__)

def query():
    if params.search.strip() == '' and (params.startDate, params.endDate) in cache:
        return cache[(params.startDate, params.endDate)]

    tic = time.time()
    params.startDateStr = params.startDate.strftime(DATE_FORMAT)
    params.endDateStr = params.endDate.strftime(DATE_FORMAT)
    sql = {'datetime': {'$lte': params.endDate, '$gte': params.startDate}}
    if params.search != '':
        # FIXME: currently no escape for sql/html
        sql['content'] = {'$regex': '.*' + params.search + '.*'}
    found = partner.find(sql)
    toc = time.time()
    print(f'MongoDB: time elsapsed = {(toc - tic)}s.')

    found = sorted(found, key=lambda msg: msg['idx'], reverse=True)
    print(f'Sort: time elsapsed = {(toc - tic)}s.')

    sess_list = []
    msg_list = []
    lastDate = params.startDate
    msgIdx2sessIdx = {0: 1}
    msgIdx2msgIdx = {0: 0}

    for msg in found:
        msg = edict(msg)
        msg.content = msg.content.replace('??', '[emoji]')
        if msg.sender == '我':
            msg.profile = args.my_profile
            if args.my_name: msg.sender = args.my_name
        else:
            msg.profile = args.your_profile
            if args.your_name: msg.sender = args.your_name

        sessIdx = len(sess_list) + 1
        msgIdx2sessIdx[msg.idx] = sessIdx

        if (msg.datetime - lastDate).seconds > 3600:
            sess = edict(msg_list=msg_list, id=f'sec{sessIdx}', number=sessIdx)
            if msg_list: sess_list.append(sess)
            msg_list = []

        if len(msg_list) > 0 and (msg_list[-1].sender == msg.sender and (msg.datetime - lastDate).seconds < 180):
            msg_list[-1].content += '\n' + msg.content
            msgIdx2msgIdx[msg.idx] = msg_list[-1].idx
        else:
            msg_list.append(msg)
            msgIdx2msgIdx[msg.idx] = msg.idx

        lastDate = msg.datetime
    
    max_page = math.ceil(len(sess_list) / status.nSessVisible)

    toc = time.time()
    print(f'Query: time elsapsed = {(toc - tic)}s.')

    ret = (sess_list, max_page, msgIdx2sessIdx, msgIdx2msgIdx)
    if params.search.strip() == '':
        cache[(params.startDate, params.endDate)] = ret

    return ret


def set_page(page):
    try:
        status.curPage = int(page)
    except:
        print('Invalid page:', page)

    if status.curPage > status.maxPage:
        status.curPage = status.maxPage

    if status.curPage < 1:
        status.curPage = 1

    status.endPage = min(status.maxPage, status.curPage + status.nPageVisible - 1)
    status.startPage = max(1, status.endPage - status.nPageVisible + 1)
    status.pages = list(range(status.startPage, status.endPage + 1))


@app.route('/msg/<msgIdx>')
def main_msg(msgIdx):
    return redirect('/?' + urllib.parse.urlencode([
        ('startDate', datetime.strftime(params.startDate, DATE_FORMAT)),
        ('endDate', datetime.strftime(params.endDate, DATE_FORMAT)),
        ('search', ''),
        ('msgIdx', msgIdx)
    ]))


@app.route('/date', methods=['GET'])
def main_date():
    targetDate = request.args['date']
    urlargs = [
        ('startDate', datetime.strftime(params.startDate, DATE_FORMAT)),
        ('endDate', datetime.strftime(params.endDate, DATE_FORMAT))]
    try:
        date = datetime.strptime(targetDate, DATE_FORMAT)
        found = partner.find({'datetime': {'$lt': date + timedelta(days=1), '$gte': date}})
        found = sorted(found, key=lambda msg: msg['idx'], reverse=True)
        msgIdx = found[0]['idx']
        urlargs += [('search', '')]
        urlargs += [('msgIdx', msgIdx)]
    except:
        urlargs += [('search', params.search)]
        urlargs += [('page', status.curPage)]
        print('Invalid date:', targetDate)
    return redirect('/?' + urllib.parse.urlencode(urlargs))


@app.route('/', methods=['GET'])
def main():
    scroll = None
    if status.sess_list is None:
        status.sess_list, status.maxPage, _, _ = query()

    # paging
    if 'page' in request.args:
        set_page(request.args['page'])
    
    # filter
    is_dirty = False

    if 'startDate' in request.args:
        startDate = request.args['startDate'].strip()
        try:
            startDate = datetime.strptime(startDate, DATE_FORMAT)
            if startDate != params.startDate: is_dirty = True
            params.startDate = startDate
        except: pass
    
    if 'endDate' in request.args:
        endDate = request.args['endDate'].strip()
        try:
            endDate = datetime.strptime(endDate, DATE_FORMAT)
            if endDate != params.endDate: is_dirty = True
            params.endDate = endDate
        except: pass

    if 'search' in request.args:
        search = request.args['search'].strip()
        if search != params.search: is_dirty = True
        params.search = search

    if is_dirty or 'msgIdx' in request.args:
        status.sess_list, status.maxPage, msgIdx2sessIdx, msgIdx2msgIdx = query()

        if 'msgIdx' in request.args:
            msgIdx = request.args['msgIdx']
            sessIdx = msgIdx2sessIdx[int(msgIdx)]
            page = (sessIdx - 1) // status.nSessVisible + 1
            scroll = f'msg{msgIdx2msgIdx[int(msgIdx)]}'

        else:
            page = 1
        set_page(page)

    # paging
    status.startSess = (status.curPage - 1) * status.nSessVisible + 1
    status.endSess = min(status.startSess + status.nSessVisible - 1, len(status.sess_list))
    status.startSessId = "sec" + str(status.startSess)
    status.endSessId = "sec" + str(status.endSess)
    sess_list = status.sess_list[status.startSess - 1 : status.endSess]

    return render_template('template.html', sess_list=sess_list, params=params, 
        status=status, args=args, scroll=scroll)


if __name__ == '__main__':
    app.run()
