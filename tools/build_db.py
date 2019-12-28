import re
import os
import json
import argparse
import subprocess
from datetime import datetime

import pymongo


def preprocess(input_path, output_path):
    print('Parsing iTools wechat record...')
    try:
        raw = open(input_path, encoding='utf-8').read()
    except UnicodeDecodeError:
        raw = subprocess.check_output([r'D:\Program Files\Git\usr\bin\iconv.exe', '-f', 'gbk', '-t', 'utf-8', '-c', input_path]).decode('utf-8')

    regex = r'(201\d-\d\d-\d\d \d\d:\d\d)'
    split = re.split(regex, raw)
    
    assert len(split) % 2 == 1
    split = split[1:]
    
    msgs = []
    for i in range(0, len(split) - 1, 2): msgs.append((split[i], split[i + 1]))
    
    # NOTE: assuming no white space in partner's wechat display name
    ans = [(time, re.findall(r'^\s*(\S+)\s+(\S+)\s+(\S+)\s+(.*)$', msg, re.DOTALL)) for time, msg in msgs]
    ans = [(time, sender, status, msgtype, content.strip()) for time, [(sender, status, msgtype, content)] in ans]

    with open(output_path, 'w', encoding='utf-8') as fout:
        for time, sender, status, msgtype, content in ans:
            fout.write(json.dumps({'time': time, 'sender': sender, 'status': status, 'type': msgtype, 'content': content}, 
                ensure_ascii=False) + '\n')
    print('Done. intermediate output:', output_path)


def build_db(filename):
    print('Building MongoDB...')
    client = pymongo.MongoClient("localhost", 27017)
    db = client.wechat
    partner = db.partner

    table = []
    with open(filename, encoding='utf-8') as fin:
        for i, line in enumerate(fin):
            record = json.loads(line)
            record['datetime'] = datetime.strptime(record['time'], "%Y-%m-%d %H:%M")
            record['idx'] = i
            table.append(record)

    partner.drop()
    partner.insert_many(table)
    partner.create_index('datetime')
    print('Done.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input_path', type=str, help='Path to wechat record file')
    parser.add_argument('-o', '--output_path', type=str, help='Path to output preprocessed file, default to [input_path].json')
    args = parser.parse_args()
    args.output_path = args.input_path + '.json' if args.output_path is None else args.output_path

    preprocess(args.input_path, args.output_path)
    build_db(args.output_path)
