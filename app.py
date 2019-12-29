import math
import time
import urllib
import argparse
from datetime import datetime, timedelta

import pymongo
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

class Object: 
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

params = Object(
    startDate=datetime.strptime(args.start_date, DATE_FORMAT),
    endDate=datetime.strptime(args.end_date, DATE_FORMAT),
    search=''
)

status = Object(
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
    sess_list = None,
    base_url = '',
)

cache = dict()

app = Flask(__name__)


def merge_and_split_messages(messages):
    sessIdx = 1
    sess_list = []
    msg_list = []
    lastDate = messages[0]['datetime'] if messages else datetime(1998, 2, 15)
    msgIdx2sessIdx = {0: 1}
    msgIdx2msgIdx = {0: 0}
    sentinel = {'datetime': datetime(2100, 1, 1), 'sender': '', 'content': '', 'idx': 1000000000}

    for i, msg in enumerate(messages + [sentinel]):
        msg = Object(**msg)
        msg.content = msg.content.replace('??', '[emoji]')
        if msg.sender == '我':
            msg.profile = args.my_profile
            msg.senderName = args.my_name if args.my_name else msg.sender
        else:
            msg.profile = args.your_profile
            msg.senderName = args.your_name if args.your_name else msg.sender

        if (msg.datetime - lastDate).seconds > 1800:
            sess = Object(msg_list=msg_list, id=f'sec{sessIdx}', number=sessIdx)
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
        print('Using cache...')
        return cache[(params.startDate, params.endDate)]

    params.startDateStr = params.startDate.strftime(DATE_FORMAT)
    params.endDateStr = params.endDate.strftime(DATE_FORMAT)
    sql = {'datetime': {'$lte': params.endDate, '$gte': params.startDate}}
    if params.search != '':
        # FIXME: currently no escape for sql/html
        sql['content'] = {'$regex': '.*' + params.search + '.*'}

    found = database.find(sql)
    found = sorted(found, key=lambda msg: msg['idx'], reverse=True)

    ret = merge_and_split_messages(found)
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


def feed(req, database, use_cache, force_refresh=False):
    scroll = None
    if status.sess_list is None:
        status.sess_list, status.maxPage, _, _ = query(database, use_cache)

    # paging
    if 'page' in req.args:
        sess_list = set_page(req.args['page'])
    else:
        sess_list = set_page(1)
    
    # filter
    is_dirty = (req.base_url != status.base_url)
    status.base_url = req.base_url
    if force_refresh: is_dirty = True

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
        print('INFO: sess_list reloaded: length =', len(status.sess_list))

        if 'msgIdx' in req.args:
            msgIdx = req.args['msgIdx']
            sessIdx = msgIdx2sessIdx[int(msgIdx)]
            page = (sessIdx - 1) // status.nSessVisible + 1
            scroll = f'msg{msgIdx2msgIdx[int(msgIdx)]}'
        else:
            page = 1
        
        sess_list = set_page(page)

    return Object(
        sess_list = sess_list,
        params = params,
        status = status,
        args = args,
        scroll = scroll
    )


@app.route('/', methods=['GET'])
def main():
    print('INFO: in main')
    kwargs = feed(request, database=partner, use_cache=True)
    return render_template('template.html', **vars(kwargs))


@app.route('/notebook', methods=['GET', 'POST'])
def main_notebook():
    print('INFO: in main notebook')

    if request.method == 'GET':
        kwargs = feed(request, database=notebook, use_cache=False, force_refresh=True)
        print('main_notebook', len(kwargs.sess_list), [sess.id for sess in kwargs.sess_list])
        return render_template('template.html', **vars(kwargs))

    else:
        print('data:', request.data)
        print('args:', request.args)
        print('forms:', request.form)
        print('json:', request.json)
        print('request:', request)
        return {}


@app.route('/favorite', methods=['GET'])
def main_favorite():
    sessId = request.args['sec']
    sessIdx = int(sessId.replace('sec', ''))

    # FIXME: ugly! find a better method to handle refresh
    database = notebook if request.args['from'] == 'notebook' else partner
    use_cache = False if request.args['from'] == 'notebook' else True
    _ = feed(request, database=database, use_cache=use_cache, force_refresh=True)
    
    sess = status.sess_list[sessIdx - 1]

    if request.args['op'] == 'add':
        n_add = 0
        for i, m in enumerate(sess.msg_list):
            try: notebook.insert_one(vars(m)); n_add += 1
            except: print(f'Add failed! index={i}, msgIdx={m.idx}')  
        print(f'Del: section {sessId}, length={len(sess.msg_list)} #add={n_add}.')
        # ajax
        kwargs = feed(request, database=notebook, use_cache=False, force_refresh=True)
        return render_template('template.html', **vars(kwargs))   

    elif request.args['op'] == 'del':
        n_del = 0
        for i, m in enumerate(sess.msg_list): 
            try: n_del += notebook.delete_one({'datetime': m.datetime}).deleted_count
            except: print(f'Del failed! index={i}, msgIdx={m.idx}')  
        print(f'Del: section {sessId}, length={len(sess.msg_list)} #del={n_del}.')
        # block
        kwargs = feed(request, database=notebook, use_cache=False, force_refresh=True)
        return render_template('template.html', **vars(kwargs))

    return 'None'


if __name__ == '__main__':
    app.run(threaded=True)
