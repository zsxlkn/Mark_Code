import threading
from multiprocessing import Pool
import os
def worker(name):
    print(f"Hello {name} 进程PID: {os.getpid()}, 线程ID: {threading.get_ident()}, 线程名: {threading.current_thread().name}")

t = threading.Thread(
    target=worker,
    args=("张三",)
)
print(f"主线程PID: {os.getpid()}, 线程ID: {threading.get_ident()}, 线程名: {threading.current_thread().name}")
t.start()