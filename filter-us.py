import datetime
import ipaddress
import json
import os
import re
import socket
import time
from pathlib import Path
from typing import Any

import requests
import yaml


# =========================================================
# 基本配置
# =========================================================

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "50lovelace/flclash-nodes/main/flclash.yaml"
)

OUTPUT_FILE = "flclash-us.yaml"
INFO_FILE = "update-info.txt"
CACHE_FILE = "risk-cache.json"

ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"

# 只保留低于该分数的节点
RISK_THRESHOLD = 25

# AbuseIPDB 统计最近多少天的举报
MAX_AGE_IN_DAYS = 90

# 缓存有效期，避免每天重复查询同一个 IP
CACHE_VALID_DAYS = 7

# 每次 API 查询间隔，避免请求过快
REQUEST_INTERVAL_SECONDS = 0.15

# 网络超时
DOWNLOAD_TIMEOUT = 60
API_TIMEOUT = 30
DNS_TIMEOUT = 10


# =========================================================
# 时间
# =========================================================

BEIJING_TIMEZONE = datetime.timezone(
    datetime.timedelta(hours=8)
)


def beijing_now() -> datetime.datetime:
    return datetime.datetime.now(BEIJING_TIMEZONE)


def current_time_text() -> str:
    return beijing_now().strftime("%Y-%m-%d %H:%M:%S")


# =========================================================
# 美国节点识别
# =========================================================

def is_us_node(name: Any) -> bool:
    """
    根据节点名称判断是否为美国节点。

    支持：
    🇺🇸
    美国
    United States
    America
    US001
    USA001
    """
    if not name:
        return False

    text = str(name)
    upper_text = text.upper()

    if "🇺🇸" in text:
        return True

    if "美国" in text:
        return True

    if "UNITED STATES" in upper_text:
        return True

    if "AMERICA" in upper_text:
        return True

    # 匹配 US、USA、US001、USA001，避免误匹配普通单词中的 us
    if re.search(
        r"(?<![A-Z])USA?(?=\d|[^A-Z]|$)",
        upper_text
    ):
        return True

    return False


# =========================================================
# 缓存处理
# =========================================================

def load_cache() -> dict[str, dict[str, Any]]:
    path = Path(CACHE_FILE)

    if not path.exists():
        return {}

    try:
        with path.open(
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data

    except (
        OSError,
        json.JSONDecodeError
    ) as error:
        print(f"读取缓存失败，将重新建立缓存：{error}")

    return {}


def save_cache(
    cache: dict[str, dict[str, Any]]
) -> None:
    with open(
        CACHE_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            cache,
            file,
            ensure_ascii=False,
            indent=2,
            sort_keys=True
        )


def cache_is_valid(
    record: dict[str, Any]
) -> bool:
    checked_at = record.get("checked_at")

    if not checked_at:
        return False

    try:
        checked_time = datetime.datetime.fromisoformat(
            str(checked_at)
        )

        if checked_time.tzinfo is None:
            checked_time = checked_time.replace(
                tzinfo=BEIJING_TIMEZONE
            )

        age = beijing_now() - checked_time

        return age < datetime.timedelta(
            days=CACHE_VALID_DAYS
        )

    except (
        TypeError,
        ValueError
    ):
        return False


# =========================================================
# IP 解析
# =========================================================

def is_public_ip(ip_text: str) -> bool:
    try:
        ip_object = ipaddress.ip_address(ip_text)

        return not (
            ip_object.is_private
            or ip_object.is_loopback
            or ip_object.is_link_local
            or ip_object.is_multicast
            or ip_object.is_reserved
            or ip_object.is_unspecified
        )

    except ValueError:
        return False


def resolve_server_to_ip(
    server: Any
) -> str | None:
    """
    server 可能是：
    1. 直接 IP
    2. 域名

    优先返回公开 IPv4；
    没有 IPv4 时再返回公开 IPv6。
    """
    if not server:
        return None

    server_text = str(server).strip()

    if not server_text:
        return None

    # server 本身就是 IP
    try:
        ip_object = ipaddress.ip_address(server_text)

        if is_public_ip(str(ip_object)):
            return str(ip_object)

        return None

    except ValueError:
        pass

    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(DNS_TIMEOUT)

    try:
        address_info = socket.getaddrinfo(
            server_text,
            None,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM
        )

        ipv4_addresses: list[str] = []
        ipv6_addresses: list[str] = []

        for result in address_info:
            family = result[0]
            ip_text = result[4][0]

            if not is_public_ip(ip_text):
                continue

            if family == socket.AF_INET:
                if ip_text not in ipv4_addresses:
                    ipv4_addresses.append(ip_text)

            elif family == socket.AF_INET6:
                if ip_text not in ipv6_addresses:
                    ipv6_addresses.append(ip_text)

        if ipv4_addresses:
            return ipv4_addresses[0]

        if ipv6_addresses:
            return ipv6_addresses[0]

        return None

    except socket.gaierror as error:
        print(
            f"域名解析失败：{server_text}，"
            f"原因：{error}"
        )
        return None

    except OSError as error:
        print(
            f"网络解析异常：{server_text}，"
            f"原因：{error}"
        )
        return None

    finally:
        socket.setdefaulttimeout(old_timeout)


# =========================================================
# AbuseIPDB 查询
# =========================================================

def query_abuseipdb(
    ip_address: str,
    api_key: str
) -> dict[str, Any] | None:
    headers = {
        "Accept": "application/json",
        "Key": api_key
    }

    params = {
        "ipAddress": ip_address,
        "maxAgeInDays": MAX_AGE_IN_DAYS,
        "verbose": ""
    }

    try:
        response = requests.get(
            ABUSEIPDB_URL,
            headers=headers,
            params=params,
            timeout=API_TIMEOUT
        )

        if response.status_code == 429:
            print(
                "AbuseIPDB 今日查询额度可能已用完，"
                "停止继续查询。"
            )
            return {
                "rate_limited": True
            }

        response.raise_for_status()

        payload = response.json()
        data = payload.get("data")

        if not isinstance(data, dict):
            print(
                f"AbuseIPDB 返回格式异常：{ip_address}"
            )
            return None

        score = data.get("abuseConfidenceScore")

        if score is None:
            print(
                f"未取得风险评分：{ip_address}"
            )
            return None

        return {
            "ip": ip_address,
            "score": int(score),
            "country_code": data.get(
                "countryCode"
            ),
            "usage_type": data.get(
                "usageType"
            ),
            "isp": data.get("isp"),
            "domain": data.get("domain"),
            "total_reports": data.get(
                "totalReports",
                0
            ),
            "last_reported_at": data.get(
                "lastReportedAt"
            ),
            "checked_at": beijing_now().isoformat()
        }

    except requests.Timeout:
        print(
            f"AbuseIPDB 查询超时：{ip_address}"
        )
        return None

    except requests.RequestException as error:
        print(
            f"AbuseIPDB 查询失败：{ip_address}，"
            f"原因：{error}"
        )
        return None

    except (
        ValueError,
        TypeError
    ) as error:
        print(
            f"AbuseIPDB 数据解析失败：{ip_address}，"
            f"原因：{error}"
        )
        return None


def get_risk_record(
    ip_address: str,
    api_key: str,
    cache: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, bool]:
    """
    返回：
    风险记录、是否达到 API 限额
    """
    cached_record = cache.get(ip_address)

    if (
        isinstance(cached_record, dict)
        and cache_is_valid(cached_record)
    ):
        return cached_record, False

    record = query_abuseipdb(
        ip_address,
        api_key
    )

    if record and record.get("rate_limited"):
        return None, True

    if record:
        cache[ip_address] = record
        save_cache(cache)

    time.sleep(REQUEST_INTERVAL_SECONDS)

    return record, False


# =========================================================
# 下载源文件
# =========================================================

def download_source() -> dict[str, Any]:
    print("开始下载原始节点配置……")

    response = requests.get(
        SOURCE_URL,
        timeout=DOWNLOAD_TIMEOUT
    )

    response.raise_for_status()

    data = yaml.safe_load(
        response.text
    )

    if not isinstance(data, dict):
        raise ValueError(
            "下载的源文件不是有效的 YAML 配置"
        )

    return data


# =========================================================
# 主程序
# =========================================================

def main() -> None:
    api_key = os.environ.get(
        "ABUSEIPDB_API_KEY",
        ""
    ).strip()

    if not api_key:
        raise RuntimeError(
            "未读取到 ABUSEIPDB_API_KEY。"
            "请检查 GitHub Actions Secret 和 env 配置。"
        )

    source_data = download_source()

    all_nodes = source_data.get(
        "proxies",
        []
    )

    if not isinstance(all_nodes, list):
        raise ValueError(
            "源配置里的 proxies 不是列表"
        )

    print(
        f"原始节点数量：{len(all_nodes)}"
    )

    us_nodes = [
        node
        for node in all_nodes
        if isinstance(node, dict)
        and is_us_node(
            node.get("name", "")
        )
    ]

    print(
        f"识别到美国节点：{len(us_nodes)}"
    )

    cache = load_cache()

    passed_nodes: list[dict[str, Any]] = []
    rejected_nodes: list[dict[str, Any]] = []
    unresolved_nodes: list[dict[str, Any]] = []
    query_failed_nodes: list[dict[str, Any]] = []

    # 同一 IP 的检测结果在本次运行中直接复用
    current_run_records: dict[
        str,
        dict[str, Any] | None
    ] = {}

    rate_limit_reached = False

    for index, node in enumerate(
        us_nodes,
        start=1
    ):
        name = str(
            node.get("name", "")
        )

        server = node.get("server")

        print(
            f"[{index}/{len(us_nodes)}] "
            f"检测：{name}"
        )

        ip_address = resolve_server_to_ip(
            server
        )

        if not ip_address:
            unresolved_nodes.append({
                "name": name,
                "server": server
            })

            print("  结果：无法解析公开 IP，排除")
            continue

        if ip_address in current_run_records:
            record = current_run_records[
                ip_address
            ]

        else:
            if rate_limit_reached:
                query_failed_nodes.append({
                    "name": name,
                    "server": server,
                    "ip": ip_address,
                    "reason": "API额度已用完"
                })
                continue

            record, limited = get_risk_record(
                ip_address,
                api_key,
                cache
            )

            if limited:
                rate_limit_reached = True

            current_run_records[
                ip_address
            ] = record

        if not record:
            query_failed_nodes.append({
                "name": name,
                "server": server,
                "ip": ip_address,
                "reason": "未取得风险评分"
            })

            print("  结果：查询失败，排除")
            continue

        score = int(
            record.get("score", 100)
        )

        if score < RISK_THRESHOLD:
            passed_nodes.append(node)

            print(
                f"  结果：通过，风险分 {score}"
            )

        else:
            rejected_nodes.append({
                "name": name,
                "server": server,
                "ip": ip_address,
                "score": score,
                "country_code": record.get(
                    "country_code"
                ),
                "usage_type": record.get(
                    "usage_type"
                ),
                "isp": record.get("isp")
            })

            print(
                f"  结果：排除，风险分 {score}"
            )

    save_cache(cache)

    passed_names = [
        str(node["name"])
        for node in passed_nodes
        if node.get("name")
    ]

    if not passed_names:
        raise RuntimeError(
            "筛选后没有任何低风险节点。"
            "risk-test 分支不会生成空订阅。"
        )

    output = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": True,
        "mode": "Rule",
        "log-level": "info",
        "unified-delay": True,

        "proxies": passed_nodes,

        "proxy-groups": [
            {
                "name": "☁️ 代理选择",
                "type": "select",
                "proxies": [
                    "🔰 手动选择",
                    "🇺🇸 美国自动"
                ]
            },
            {
                "name": "🔰 手动选择",
                "type": "select",
                "proxies": (
                    ["🇺🇸 美国自动"]
                    + passed_names
                )
            },
            {
                "name": "🇺🇸 美国自动",
                "type": "url-test",
                "url": (
                    "https://www.gstatic.com/"
                    "generate_204"
                ),
                "interval": 300,
                "tolerance": 50,
                "proxies": passed_names
            }
        ],

        "rules": [
            "MATCH,☁️ 代理选择"
        ]
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        yaml.safe_dump(
            output,
            file,
            allow_unicode=True,
            sort_keys=False
        )

    info_lines = [
        "FlClash 美国低风险节点订阅",
        "",
        f"北京时间：{current_time_text()}",
        "",
        f"风险门槛：AbuseIPDB < {RISK_THRESHOLD}",
        f"缓存有效期：{CACHE_VALID_DAYS} 天",
        "",
        f"原始节点数量：{len(all_nodes)}",
        f"美国节点数量：{len(us_nodes)}",
        f"低风险保留：{len(passed_nodes)}",
        f"高风险排除：{len(rejected_nodes)}",
        f"无法解析排除：{len(unresolved_nodes)}",
        f"查询失败排除：{len(query_failed_nodes)}",
        f"缓存IP数量：{len(cache)}",
        "",
        "说明：",
        "1. 风险评分采用 AbuseIPDB abuseConfidenceScore。",
        "2. 只保留风险分小于25的节点。",
        "3. 当前检测的是配置中的 server IP，"
        "不一定等于代理真实出口IP。",
        "4. 查询失败的节点不会进入正式订阅。",
        "",
        "来源：",
        "50lovelace/flclash-nodes"
    ]

    with open(
        INFO_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(
            "\n".join(info_lines)
            + "\n"
        )

    # 输出详细排除报告，方便 risk-test 检查
    report = {
        "generated_at": current_time_text(),
        "risk_threshold": RISK_THRESHOLD,
        "passed_count": len(passed_nodes),
        "rejected_count": len(rejected_nodes),
        "unresolved_count": len(
            unresolved_nodes
        ),
        "query_failed_count": len(
            query_failed_nodes
        ),
        "rejected_nodes": rejected_nodes,
        "unresolved_nodes": unresolved_nodes,
        "query_failed_nodes": (
            query_failed_nodes
        )
    }

    with open(
        "risk-report.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("")
    print("风险筛选完成")
    print(
        f"低风险保留：{len(passed_nodes)}"
    )
    print(
        f"高风险排除：{len(rejected_nodes)}"
    )
    print(
        f"无法解析：{len(unresolved_nodes)}"
    )
    print(
        f"查询失败：{len(query_failed_nodes)}"
    )


if __name__ == "__main__":
    main()
