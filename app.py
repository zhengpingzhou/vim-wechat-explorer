import math
import http
import argparse
from datetime import datetime, timedelta

from flask import Flask
from flask import request, render_template

from lib.utils import Object
from lib.utils import date2str, str2date
from lib.db import Database

parser = argparse.ArgumentParser()
parser.add_argument('--my-name', dest='myName', type=str, default='')
parser.add_argument('--your-name', dest='yourName', type=str, default='')
parser.add_argument('--my-profile', dest='myProfile', type=str, default='me.png', help='filename of customized profile. must be under static/img/.')
parser.add_argument('--your-profile', dest='yourProfile', type=str, default='you.png', help='filename of customized profile. must be under static/img/.')
parser.add_argument('--start-date', dest='startDate', type=str, default='2000-01-01')
parser.add_argument('--end-date', dest='endDate', type=str, default='2100-01-01')
parser.add_argument('--hide-control', dest='hideControl', action='store_true', help='set to hide control panel on default.')
args = parser.parse_args()

app = Flask(__name__)

cfg = Object(
    URL_MAIN = '/main', ID_MAIN = 'main',
    URL_NOTEBOOK = '/notebook', ID_NOTEBOOK = 'notebook',
    N_SEC_PER_VIEW = 10,
    N_PAGE_PER_VIEW = 6,
    EMPTY_RESPONSE = '{}'
)
db = {
    cfg.ID_MAIN: Database(args, cfg.ID_MAIN, use_cache=True), 
    cfg.ID_NOTEBOOK: Database(args, cfg.ID_NOTEBOOK, use_cache=False)
}


def Render(VIEW):
    return render_template('template.html', VIEW=VIEW,
        URL_NOTEBOOK=cfg.URL_NOTEBOOK, URL_MAIN=cfg.URL_MAIN, hideControl=args.hideControl)


def GoPage(viewUrl, viewId, page, anchor=None, **kwargs):
    page = int(page)
    result = db[viewId].query(preprocess=True, **kwargs)

    VIEW = Object(baseUrl=viewUrl, anchor=anchor)
    VIEW.curPage = page
    VIEW.maxPage = math.ceil(len(result.secList) / cfg.N_SEC_PER_VIEW)
    VIEW.minPage = 1
    VIEW.endPage = min(VIEW.maxPage, VIEW.curPage + cfg.N_PAGE_PER_VIEW - 1)
    VIEW.startPage = max(1, VIEW.endPage - cfg.N_PAGE_PER_VIEW + 1)
    VIEW.pages = list(range(VIEW.startPage, VIEW.endPage + 1))
    
    VIEW.startSecIdx = (VIEW.curPage - 1) * cfg.N_SEC_PER_VIEW + 1
    VIEW.endSecIdx = min(VIEW.startSecIdx + cfg.N_SEC_PER_VIEW - 1, len(result.secList))
    VIEW.startSec = "sec" + str(VIEW.startSecIdx)
    VIEW.endSec = "sec" + str(VIEW.endSecIdx)
    VIEW.secList = result.secList[VIEW.startSecIdx - 1 : VIEW.endSecIdx]

    VIEW.startDate = result.startDate
    VIEW.endDate = result.endDate
    VIEW.startDateStr = date2str(VIEW.startDate)
    VIEW.endDateStr = date2str(VIEW.endDate)
    VIEW.search = result.search
    return Render(VIEW)


def GoQuery(viewUrl, viewId, **kwargs):
    return GoPage(viewUrl, viewId, page=1, **kwargs)


def GoMessage(viewUrl, viewId, msgIdx):
    result = db[viewId].query(preprocess=True, search='')
    secIdx = result.msg2sec[msgIdx]
    parentMsgIdx = result.msg2parent[msgIdx]
    page = (secIdx - 1) // cfg.N_SEC_PER_VIEW + 1
    anchor = 'msg' + str(parentMsgIdx)
    return GoPage(viewUrl, viewId, page, anchor=anchor)


def GoDate(viewUrl, viewId, date):
    result = db[viewId].query(preprocess=False, date=date)
    if result.msgList: 
        msgIdx = result.msgList[0]['idx']
        return GoMessage(viewUrl, viewId, msgIdx)
    else:
        return ('', http.HTTPStatus.NO_CONTENT)


def DoNotebook(viewUrl, viewId, secId, operation):
    secIdx = int(secId.replace('sec', ''))
    result = db[viewId].query(preprocess=True)
    sec = result.secList[secIdx - 1]

    if operation == 'add':
        cnt = db[cfg.ID_NOTEBOOK].insertMany(sec.msgList)
    elif operation == 'del':
        cnt = db[cfg.ID_NOTEBOOK].deleteMany(sec.msgList)
    
    print('op:', operation, 'sec:', secId, '#messages:', cnt)
    return cfg.EMPTY_RESPONSE


def Response(viewUrl, viewId):
    if request.method == 'GET':
        if 'page' in request.args:
            return GoPage(viewUrl, viewId, int(request.args['page']))
        elif 'msgIdx' in request.args:
            return GoMessage(viewUrl, viewId, int(request.args['msgIdx']))
        elif 'date' in request.args:
            return GoDate(viewUrl, viewId, request.args['date'])
        else:
            return GoQuery(viewUrl, viewId, **request.args)
    else:
        return DoNotebook(viewUrl, viewId, **request.form)


@app.route(cfg.URL_MAIN, methods=['GET', 'POST'])
def Main():
    return Response(cfg.URL_MAIN, cfg.ID_MAIN)


@app.route(cfg.URL_NOTEBOOK, methods=['GET', 'POST'])
def Notebook():
    return Response(cfg.URL_NOTEBOOK, cfg.ID_NOTEBOOK)


if __name__ == '__main__':
    app.run(threaded=True)
