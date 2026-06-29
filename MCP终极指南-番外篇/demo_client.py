"""
FastAPI 入门 Demo —— 客户端
运行方式（另开一个终端）: python demo_client.py
"""

import httpx
import json

BASE_URL = "http://localhost:8000"


def test_get():
    """测试 GET 请求"""
    print("=" * 40)
    resp = httpx.get(f"{BASE_URL}/zsx")
    print("响应:", resp.json())


def test_post_chat():
    """测试普通 POST 请求"""
    print("\n" + "=" * 40)
    resp = httpx.post(f"{BASE_URL}/chat", json={"message": "FastAPI 好学吗？"} )
    print("响应:", resp.json())


def test_stream():
    """测试流式响应（SSE）"""
    print("\n" + "=" * 40)
    with httpx.stream( "POST", f"{BASE_URL}/stream",json={"message": "你知道流式传输怎么工作"},timeout=30) as resp:
        for line in resp.iter_lines():
            # 将 HTTP 响应体按行（\n 换行符）分割，每次迭代返回一行字符串。在 HTTP 响应中，行是由换行符 \n 或 \r\n 分隔的：
            # print("line=",line)
            if not line:
                continue
            if line.startswith("data:"):
                # SSE 协议规定数据行必须以 data: 开头
                # .strip()移除字符串首尾的空白字符（空格、换行、制表符等）
                raw = line.removeprefix("data:").strip()
                try:
                    data = json.loads(raw)
                    if "delta" in data:
                        print(data["delta"], end="", flush=True)
                    elif data.get("status") == "done":
                        print("\n[流式传输结束]")
                except json.JSONDecodeError:
                    pass


if __name__ == "__main__":
    test_get()
    test_post_chat()
    test_stream()
