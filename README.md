# vim-wechat-explorer

![screenshot](static/img/screenshot.png)

## Usage

1. Export WeChat txt record from iTools (works for iOS): https://www.zhihu.com/question/20776328/answer/716902617
2. Visualization with this tool (Requirement: Ubuntu 18.04 LTS + Python 3.6):

``` bash
git clone https://github.com/zhengpingzhou/vim-wechat-explorer.git
cd vim-wechat-explorer

# environment setup
sudo apt install mongodb
sudo service mongodb start
pip3 install --local flask pymongo easydict

# database setup
python3 tools/build_db.py -i /path/to/exported/itools/wechat/file

# launch flask server, then goto http://127.0.0.1:5000/
# customized profile images must be put into `static/img/`
python3 app.py [--hide-control] [--my-name="我的名字" --your-name="你的名字" --my-profile="profile1.jpg" --your-profile="profile2.jpg"]
```

## Features

- Merge messages within an interval of 3 minutes
- Split messages into sessions within an interval of 1 hour
- Vim-like key mapping:
  - `h / j / k / l`: previous page / scroll down / scroll up / next page
  - `^b / ^f`: previous section / next section
  - `b / e`: enter begin date / end date
  - `slash`: enter search phrase (supports regex)
  - `colon`: enter page number
  - `esc`: defocus (in insert mode) / hide control panel (in normal mode)

