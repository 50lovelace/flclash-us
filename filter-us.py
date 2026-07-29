import yaml
import datetime
import requests


# ==========================
# 配置
# ==========================

SOURCE_URL = "https://raw.githubusercontent.com/50lovelace/flclash-nodes/main/flclash.yaml"

OUTPUT_FILE = "flclash-us.yaml"

INFO_FILE = "update-info.txt"



# ==========================
# 美国节点判断
# ==========================

def is_us_node(name):

    if not name:
        return False

    name = str(name)


    keywords = [

        "🇺🇸",
        "美国",
        "US",
        "USA",
        "United States",
        "America"

    ]


    for k in keywords:

        if k.lower() in name.lower():

            return True


    return False



# ==========================
# 下载原始订阅
# ==========================

print("开始下载节点...")


response = requests.get(
    SOURCE_URL,
    timeout=30
)


data = yaml.safe_load(
    response.text
)



all_nodes = data.get(
    "proxies",
    []
)



print(
    "原始节点数量:",
    len(all_nodes)
)



# ==========================
# 筛选美国节点
# ==========================

us_nodes = []


for node in all_nodes:


    name = node.get(
        "name",
        ""
    )


    if is_us_node(name):

        us_nodes.append(node)



print(
    "美国节点数量:",
    len(us_nodes)
)



# ==========================
# 节点名称列表
# ==========================

us_names = [

    node["name"]

    for node in us_nodes

]



# ==========================
# 生成 Clash 配置
# ==========================

output = {


    "port": 7890,

    "socks-port": 7891,

    "allow-lan": True,

    "mode": "Rule",

    "log-level": "info",

    "unified-delay": True,


    "proxies": us_nodes,



    "proxy-groups": [



        {

            "name": "☁️ 代理选择",

            "type": "select",

            "proxies":[

                "🔰 手动选择",

                "🇺🇸 美国自动"

            ]

        },



        {

            "name": "🔰 手动选择",

            "type": "select",

            "proxies":[

                "🇺🇸 美国自动"

            ]

            +

            us_names

        },



        {

            "name": "🇺🇸 美国自动",

            "type": "url-test",

            "url":
            "https://www.gstatic.com/generate_204",

            "interval":300,

            "tolerance":50,

            "proxies":us_names

        }



    ],


    "rules":[

        "MATCH,☁️ 代理选择"

    ]


}



# ==========================
# 输出 YAML
# ==========================

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



# ==========================
# 更新说明
# ==========================

now = datetime.datetime.now().strftime(

    "%Y-%m-%d %H:%M:%S"

)



info = f"""

FlClash 美国节点订阅


更新时间:
{now}


原始节点:
{len(all_nodes)}


美国节点:
{len(us_nodes)}


生成内容:

✓ 全部美国节点保留

✓ 美国自动测速

✓ 手动选择

✓ FlClash兼容


来源:

flclash-nodes

"""


with open(

    INFO_FILE,

    "w",

    encoding="utf-8"

) as f:

    f.write(info)



print("生成完成")
