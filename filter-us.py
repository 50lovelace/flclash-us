import yaml
import datetime
import re


# 来源文件
SOURCE_URL = "https://raw.githubusercontent.com/50lovelace/flclash-nodes/main/flclash.yaml"

# 输出文件
OUTPUT_FILE = "flclash-us.yaml"
INFO_FILE = "update-info.txt"


# 美国关键词
US_KEYWORDS = [
    "US",
    "United States",
    "America",
    "美国",
    "Los Angeles",
    "LA",
    "San Jose",
    "Seattle",
    "New York",
    "Chicago"
]


# 风险关键词
BLOCK_KEYWORDS = [
    "bot",
    "test",
    "trial",
    "expired",
    "过期",
    "剩余",
    "官网",
    "客服",
    "群",
    "邀请"
]


def is_us_node(name):

    name = str(name)

    # 排除风险名称
    for word in BLOCK_KEYWORDS:
        if word.lower() in name.lower():
            return False


    # 判断美国
    for word in US_KEYWORDS:
        if word.lower() in name.lower():
            return True


    return False



# 下载原始节点
import requests

print("正在下载节点...")
response = requests.get(SOURCE_URL)

data = yaml.safe_load(response.text)


nodes = data.get("proxies", [])


us_nodes = []


for node in nodes:

    name = node.get("name", "")

    if is_us_node(name):
        us_nodes.append(node)



print("筛选完成:", len(us_nodes))


# 生成订阅

output = {
    "proxies": us_nodes,
    "proxy-groups": [
        {
            "name": "美国节点",
            "type": "select",
            "proxies": [
                node["name"]
                for node in us_nodes
            ]
        }
    ]
}


with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    yaml.dump(
        output,
        f,
        allow_unicode=True,
        sort_keys=False
    )



# 更新时间

now = datetime.datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)


info = f"""
FlClash 美国节点订阅

更新时间：
{now}

节点数量：
{len(us_nodes)}

筛选规则：
- 美国节点
- 风险关键词过滤

来源：
flclash-nodes
"""


with open(
    INFO_FILE,
    "w",
    encoding="utf-8"
) as f:

    f.write(info)



print("完成")
