import yaml
import datetime
import requests


# =========================
# 配置
# =========================

# 来源仓库
SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "50lovelace/flclash-nodes/main/flclash.yaml"
)


# 输出文件
OUTPUT_FILE = "flclash-us.yaml"

INFO_FILE = "update-info.txt"



# =========================
# 美国关键词
# =========================

US_KEYWORDS = [

    "US",
    "USA",
    "United States",
    "America",
    "美国",

    "Los Angeles",
    "LA",
    "San Jose",
    "San Francisco",
    "Seattle",

    "New York",
    "Chicago",
    "Dallas",
    "Miami"

]



# =========================
# 风险关键词
# =========================

BLOCK_KEYWORDS = [

    "bot",
    "test",
    "trial",

    "expired",
    "expire",

    "过期",
    "剩余",

    "官网",
    "客服",
    "群",
    "邀请",

    "免费",
    "公益"

]



# =========================
# 判断美国节点
# =========================

def is_us_node(name):

    name = str(name)


    # 风险过滤

    for word in BLOCK_KEYWORDS:

        if word.lower() in name.lower():

            return False



    # 美国判断

    for word in US_KEYWORDS:

        if word.lower() in name.lower():

            return True



    return False




# =========================
# 下载节点
# =========================

print("正在下载节点...")


response = requests.get(
    SOURCE_URL,
    timeout=30
)


data = yaml.safe_load(
    response.text
)



nodes = data.get(
    "proxies",
    []
)



print(
    "原始节点数量:",
    len(nodes)
)



# =========================
# 筛选美国节点
# =========================

us_nodes = []


for node in nodes:


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




# =========================
# 生成配置
# =========================


node_names = [

    node["name"]

    for node in us_nodes

]



output = {


    "proxies": us_nodes,



    "proxy-groups": [


        {

            "name":
            "🇺🇸 美国自动",


            "type":
            "url-test",


            # 测速地址

            "url":
            "http://www.gstatic.com/generate_204",


            # 5分钟检测一次

            "interval":
            300,


            # 延迟差距50ms以内不切换

            "tolerance":
            50,


            "proxies":
            node_names

        },



        {


            "name":
            "美国节点手动",


            "type":
            "select",


            "proxies":

            [

                "🇺🇸 美国自动"

            ]

            +

            node_names


        }

    ]

}



# =========================
# 写入yaml
# =========================


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




# =========================
# 更新时间
# =========================


now = datetime.datetime.now().strftime(

    "%Y-%m-%d %H:%M:%S"

)



info = f"""

FlClash 美国自动节点订阅


更新时间:

{now}



原始节点:

{len(nodes)}



美国节点:

{len(us_nodes)}



功能:

✓ 美国节点自动筛选

✓ 风险关键词过滤

✓ 延迟自动测试

✓ 自动选择最快节点



来源:

flclash-nodes

"""



with open(

    INFO_FILE,

    "w",

    encoding="utf-8"

) as f:


    f.write(info)



print(
    "生成完成"
)
