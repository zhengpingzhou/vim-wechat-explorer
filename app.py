import math
import time
import urllib
import argparse
from datetime import datetime

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

params = edict(
    startDate=datetime.strptime(args.start_date, "%Y-%m-%d"),
    endDate=datetime.strptime(args.end_date, "%Y-%m-%d"),
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

app = Flask(__name__)

def query():
    tic = time.time()
    params.startDateStr = params.startDate.strftime("%Y-%m-%d")
    params.endDateStr = params.endDate.strftime("%Y-%m-%d")
    sql = {'datetime': {'$lte': params.endDate, '$gte': params.startDate}}
    if params.search != '':
        # FIXME: currently no escape for sql/html
        sql['content'] = {'$regex': '.*' + params.search + '.*'}
    found = partner.find(sql)
    found = sorted(found, key=lambda msg: msg['idx'], reverse=True)

    sess_list = []
    msg_list = []
    lastDate = params.startDate
    msgIdx2sessIdx = dict()
    msgIdx2msgIdx = dict()

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

    return sess_list, max_page, msgIdx2sessIdx, msgIdx2msgIdx


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


@app.route('/msg/<idx>')
def main_msg(idx):
    return redirect('/?' + urllib.parse.urlencode([
        ('startDate', datetime.strftime(params.startDate, "%Y-%m-%d")),
        ('endDate', datetime.strftime(params.endDate, "%Y-%m-%d")),
        ('search', ''),
        ('msgId', idx)
    ]))


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
            startDate = datetime.strptime(startDate, "%Y-%m-%d")
            if startDate != params.startDate: is_dirty = True
            params.startDate = startDate
        except: pass
    
    if 'endDate' in request.args:
        endDate = request.args['endDate'].strip()
        try:
            endDate = datetime.strptime(endDate, "%Y-%m-%d")
            if endDate != params.endDate: is_dirty = True
            params.endDate = endDate
        except: pass

    if 'search' in request.args:
        search = request.args['search'].strip()
        if search != params.search: is_dirty = True
        params.search = search

    if is_dirty:
        status.sess_list, status.maxPage, msgIdx2sessIdx, msgIdx2msgIdx = query()
        if 'msgId' in request.args:
            msgId = request.args['msgId']
            sessIdx = msgIdx2sessIdx[int(msgId)]
            page = (sessIdx - 1) // status.nSessVisible + 1
            scroll = f'msg{msgIdx2msgIdx[int(msgId)]}'
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
