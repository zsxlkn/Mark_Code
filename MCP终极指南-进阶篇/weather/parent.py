# parent.py

import subprocess
import time
import os

pid = os.getpid()
proc = subprocess.Popen(
    ["python", "child.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True
)

# 读取 child 的第一句输出
print(f"Parent PID: {pid},得到子进程的第一个消息： {proc.stdout.readline().strip()}")

time.sleep(2)

print("发送 Hello")

proc.stdin.write("Hello\n")
proc.stdin.flush()

# 读取 child 的响应
print(f"Parent PID: {pid},得到子进程消息: {proc.stdout.readline().strip()}")

time.sleep(2)

print("发送 MCP")

proc.stdin.write("MCP\n")
proc.stdin.flush()

print(f"Parent PID: {pid},得到子进程消息: {proc.stdout.readline().strip()}")

proc.stdin.close()
proc.wait()