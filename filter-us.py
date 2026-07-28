import yaml
import datetime
import requests
import re


# ===============================
# 配置
# ===============================

SOURCE_URL = "https://raw.githubusercontent.com/50lovelace/flclash-nodes/main/flclash.yaml"

OUTPUT_FILE = "flclash-us.yaml"

INFO_FILE = "update-info.txt"



# ===============================
# 美国识别关键词
# ===============================

US_KEYWORDS = [
    "🇺🇸",
    "美国",
    "US",
    "USA",
    "America"
]


# ===============================
# 风险关键词
# ===============================

BLOCK_KEYWORDS = [
    "危险",
    "risk",
    "test",
    "trial",
    "bot",
    "expired",
    "过期",
    "剩余",
    "官网",
    "客服",
    "邀请",
    "群"
]



# ===============================
# 判断美国节点
# ===============================

def is_us(name):

    name = str(name)


    for k in BLOCK_KEYWORDS:
        if k.lower() in name.lower():
            return False


    for k in US_KEYWORDS:
        if k.lower() in name.lower():
            return True


    return False



# ===============================
# 提取速度
# ===============================

def get_speed(name):

    name = str(name)

    # 匹配：
    # 5.42MB/s
    # 4.71 MB/s

    result = re.search(
        r"([\d\.]+)\s*MB/s",
        name
    )


    if result:

        return float(result.group(1))


    # 没速度默认最低

    return 0



# ===============================
# 下载源节点
# ===============================

print("下载节点文件...")


r = requests.get(
    SOURCE_URL,
    timeout=30
)


data = yaml.safe_load(
    r.text
)



nodes = data.get(
    "proxies",
    []
)



print(
    "总节点:",
    len(nodes)
)



# ===============================
# 筛选美国
# ===============================


us_nodes=[]


for node in nodes:

    name=node.get(
        "name",
        ""
    )


    if is_us(name):

        us_nodes.append(node)



print(
    "美国有效节点:",
    len(us_nodes)
)



# ===============================
# 按速度排序
# ===============================

us_nodes.sort(
    key=lambda x:get_speed(
        x.get("name","")
    ),
    reverse=True
)



# ===============================
# 前50高速节点测速
# ===============================

fast_nodes = us_nodes[:50]



names=[
    x["name"]
    for x in fast_nodes
]



# ===============================
# 输出 Clash配置
# ===============================

output={

    "proxies":fast_nodes,


    "proxy-groups":[

        {

            "name":"🇺🇸 美国自动",

            "type":"url-test",

            "url":"https://www.gstatic.com/generate_204",

            "interval":300,

            "tolerance":50,

            "proxies":names

        },


        {

            "name":"🇺🇸 美国手动",

            "type":"select",

            "proxies":[
                "🇺🇸 美国自动"
            ]+names

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



# ===============================
# 更新时间
# ===============================

now=datetime.datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)



info=f"""
FlClash 美国节点订阅

更新时间:
{now}


筛选结果:

源节点:
{len(nodes)}

美国节点:
{len(us_nodes)}

高速节点:
{len(fast_nodes)}


规则:

✓ 美国节点
✓ 删除危险节点
✓ 删除测试节点
✓ 按速度排序
✓ 自动测速选择最快


来源:
50lovelace/flclash-nodes

"""


with open(
    INFO_FILE,
    "w",
    encoding="utf-8"
) as f:

    f.write(info)



print("完成")
