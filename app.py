import math
import argparse
from datetime import datetime

import pymongo
from easydict import EasyDict as edict

from flask import Flask, request, render_template, redirect

parser = argparse.ArgumentParser()
parser.add_argument('--my-name', type=str, default='')
parser.add_argument('--your-name', type=str, default='')
parser.add_argument('--my-profile', type=str, default='me.png')
parser.add_argument('--your-profile', type=str, default='you.png')
args = parser.parse_args()

client = pymongo.MongoClient("localhost", 27017)
db = client.wechat 
partner = db.partner 

params = edict(
    startDate=datetime(2018, 6, 27),
    endDate=datetime(2019, 6, 30),
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
    last = datetime(1998, 2, 15)

    for msg in found:
        msg = edict(msg)
        if msg.sender == '我':
            msg.profile = args.my_profile
            if args.my_name: msg.sender = args.my_name
        else:
            msg.profile = args.your_profile
            if args.your_name: msg.sender = args.your_name

        if (msg.datetime - last).seconds > 3600:
            sess = edict(msg_list=msg_list, id=f'sec{len(sess_list) + 1}', number=len(sess_list) + 1)
            if msg_list: sess_list.append(sess)
            msg_list = []

        if len(msg_list) > 0 and (msg_list[-1].sender == msg.sender and (msg.datetime - last).seconds < 180):
            msg_list[-1].content += '\n' + msg.content
        else:
            msg_list.append(msg)

        last = msg.datetime
    
    max_page = math.ceil(len(sess_list) / status.nSessVisible)
    return sess_list, max_page

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

@app.route('/', methods=['GET', 'POST'])
def main():
    if status.sess_list is None:
        status.sess_list, status.maxPage = query()

    # paging
    if request.method == 'GET':
        set_page(request.args.get('page'))
    
    # filter
    elif request.method == 'POST':
        startDate = request.form['startDate'].strip()
        endDate = request.form['endDate'].strip()
        search = request.form['search'].strip()
        try:
            params.startDate = datetime.strptime(startDate, "%Y-%m-%d")
            params.endDate = datetime.strptime(endDate, "%Y-%m-%d")
        except:
            pass
        params.search = search
        status.sess_list, status.maxPage = query()
        return redirect('/?page=1')

    # paging
    status.startSess = (status.curPage - 1) * status.nSessVisible + 1
    status.endSess = min(status.startSess + status.nSessVisible - 1, len(status.sess_list))
    status.startSessId = "sec" + str(status.startSess)
    status.endSessId = "sec" + str(status.endSess)
    sess_list = status.sess_list[status.startSess - 1 : status.endSess]

    return render_template('template.html', sess_list=sess_list, params=params, status=status)

if __name__ == '__main__':
    app.run()
