# child.py

import sys
import os

pid = os.getpid()
print(f"Child Started with PID: {pid}", flush=True)
while True:
    line = sys.stdin.readline()
    if not line:
        break
    print(f"PID {pid} 收到: {line.strip()}", flush=True)