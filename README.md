# vim-wechat-explorer

一个简单的微信聊天记录浏览器。支持日期查找、正则查找、对话收藏。适用于iTools从iOS导出的文本记录。

测试环境：Ubuntu 18.04 /  Python 3.6+。

<img src="static/img/screenshot.png" alt="screenshot" style="zoom:150%;" />

## 使用方法

1. [使用iTools从iOS导出文本聊天记录](https://www.zhihu.com/question/20776328/answer/716902617)。
2. 使用此工具进行浏览：

``` bash
# 环境配置
sudo apt install mongodb
sudo service mongodb start
pip3 install --local flask pymongo

# 数据库建立
python3 tools/build_db.py -i /path/to/txt/file/exported/from/iTools

# 启动Flask服务器，然后从浏览器打开 http://127.0.0.1:5000/
python3 app.py
```

## 基本功能

- 将间隔不超过3分钟的聊天记录合并为一条
- 将间隔超过30分钟的聊天记录分割成段
- 双击聊天记录，跳转进入其上下文
- 热键绑定：
  - `h / j / k / l`：上一页/向下滚动/向上滚动/下一页
  - `b / f`：下一段 / 上一段
  - `leftarrow/rightarrow`：上一url / 下一url
  - `正斜线`：输入搜索关键字（支持正则表达式）
  - `:` 输入目标日期
  - `esc`：取消聚焦或隐藏控制面板
  - `n`：进入收藏夹（使用`leftarrow`退出收藏夹）
  - `a`：添加当前段到收藏夹（或单击该段末尾的“+”按钮）
  - `d`：将当前段从收藏夹删除（或单击该段末尾的“回收站”按钮）

## 配置选项

```bash
usage: app.py [-h] [--my-name MY_NAME] [--your-name YOUR_NAME]
              [--my-profile MY_PROFILE] [--your-profile YOUR_PROFILE]
              [--start-date START_DATE] [--end-date END_DATE] [--hide-control]

optional arguments:
  # 查看帮助
  -h, --help             show this help message and exit
  # 自己的显示名称
  --my-name 			MY_NAME
  # 对方的显示名称
  --your-name 			YOUR_NAME
  # 自己的头像文件名，必须被放置于static/img目录下
  --my-profile 			MY_PROFILE
                        	filename of customized profile. must be under static/img/.
  # 对方的头像文件名，必须被放置于static/img目录下
  --your-profile 		YOUR_PROFILE
                        	filename of customized profile. must be under static/img/.
  # 起始日期：YYYY-MM-DD格式
  --start-date 			START_DATE
  # 终止日期：YYYY-MM-DD格式
  --end-date 			END_DATE
  # 默认隐藏控制面板
  --hide-control         set to hide control panel on default.
```

## TODO

- 对聊天记录进行html转义
- 对搜索框进行sql转义
- 文本选择、复制、粘贴
- url识别