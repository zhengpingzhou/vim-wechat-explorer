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
notebook = db.notebook

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


def merge_and_split_messages(messages):
    sessIdx = 1
    sess_list = []
    msg_list = []
    lastDate = params.startDate
    msgIdx2sessIdx = {0: 1}
    msgIdx2msgIdx = {0: 0}

    for msg in messages:
        msg = edict(msg)
        msg.content = msg.content.replace('??', '[emoji]')
        if msg.sender == '我':
            msg.profile = args.my_profile
            if args.my_name: msg.sender = args.my_name
        else:
            msg.profile = args.your_profile
            if args.your_name: msg.sender = args.your_name

        if (msg.datetime - lastDate).seconds > 3600:
            sess = edict(msg_list=msg_list, id=f'sec{sessIdx}', number=sessIdx)
            if msg_list: sess_list.append(sess)
            msg_list = []

        sessIdx = len(sess_list) + 1
        msgIdx2sessIdx[msg.idx] = sessIdx

        if len(msg_list) > 0 and (msg_list[-1].sender == msg.sender and (msg.datetime - lastDate).seconds < 180):
            msg_list[-1].content += '\n' + msg.content
            msgIdx2msgIdx[msg.idx] = msg_list[-1].idx
        else:
            msg_list.append(msg)
            msgIdx2msgIdx[msg.idx] = msg.idx

        lastDate = msg.datetime
    
    max_page = math.ceil(len(sess_list) / status.nSessVisible)
    return sess_list, max_page, msgIdx2sessIdx, msgIdx2msgIdx


def query(database, use_cache):
    if use_cache and params.search.strip() == '' and (params.startDate, params.endDate) in cache:
        return cache[(params.startDate, params.endDate)]

    tic = time.time()
    params.startDateStr = params.startDate.strftime(DATE_FORMAT)
    params.endDateStr = params.endDate.strftime(DATE_FORMAT)
    sql = {'datetime': {'$lte': params.endDate, '$gte': params.startDate}}
    if params.search != '':
        # FIXME: currently no escape for sql/html
        sql['content'] = {'$regex': '.*' + params.search + '.*'}
    found = database.find(sql)
    toc = time.time()
    print(f'MongoDB: time elsapsed = {(toc - tic)}s.')

    found = sorted(found, key=lambda msg: msg['idx'], reverse=True)
    print(f'Sort: time elsapsed = {(toc - tic)}s.')

    ret = merge_and_split_messages(found)
    toc = time.time()
    print(f'Query: time elsapsed = {(toc - tic)}s.')

    if use_cache and params.search.strip() == '':
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

    status.startSess = (status.curPage - 1) * status.nSessVisible + 1
    status.endSess = min(status.startSess + status.nSessVisible - 1, len(status.sess_list))
    status.startSessId = "sec" + str(status.startSess)
    status.endSessId = "sec" + str(status.endSess)
    sess_list = status.sess_list[status.startSess - 1 : status.endSess]
    return sess_list


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


def feed(req, database, use_cache):
    scroll = None
    if status.sess_list is None:
        status.sess_list, status.maxPage, _, _ = query(database, use_cache)

    # paging
    if 'page' in req.args:
        sess_list = set_page(req.args['page'])
    else:
        sess_list = set_page(1)
    
    # filter
    is_dirty = False

    if 'startDate' in req.args:
        startDate = req.args['startDate'].strip()
        try:
            startDate = datetime.strptime(startDate, DATE_FORMAT)
            if startDate != params.startDate: is_dirty = True
            params.startDate = startDate
        except: pass
    
    if 'endDate' in req.args:
        endDate = req.args['endDate'].strip()
        try:
            endDate = datetime.strptime(endDate, DATE_FORMAT)
            if endDate != params.endDate: is_dirty = True
            params.endDate = endDate
        except: pass

    if 'search' in req.args:
        search = req.args['search'].strip()
        if search != params.search: is_dirty = True
        params.search = search

    if is_dirty or 'msgIdx' in req.args:
        status.sess_list, status.maxPage, msgIdx2sessIdx, msgIdx2msgIdx = query(database, use_cache)

        if 'msgIdx' in req.args:
            msgIdx = req.args['msgIdx']
            sessIdx = msgIdx2sessIdx[int(msgIdx)]
            page = (sessIdx - 1) // status.nSessVisible + 1
            scroll = f'msg{msgIdx2msgIdx[int(msgIdx)]}'
        else:
            page = 1
        
        sess_list = set_page(page)

    return edict(
        sess_list = sess_list,
        params = params,
        status = status,
        args = args,
        scroll = scroll
    )


@app.route('/', methods=['GET'])
def main():
    kwargs = feed(request, database=partner, use_cache=True)
    return render_template('template.html', **kwargs)


@app.route('/notebook', methods=['GET'])
def main_notebook():
    kwargs = feed(request, database=notebook, use_cache=False)
    return render_template('template.html', **kwargs)


@app.route('/favorite', methods=['GET'])
def main_favorite():
    if 'add' in request.args:
        sessId = request.args['add']
        sessIdx = int(sessId.replace('sec', ''))
        sess = status.sess_list[sessIdx - 1]
        notebook.insert_many(sess)
        print('Add:', sessId, sessIdx, len(sess))

    elif 'del' in request.args:
        pass

    return None


if __name__ == '__main__':
    app.run()
