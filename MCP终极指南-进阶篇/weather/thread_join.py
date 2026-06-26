import threading
import time

def work():
    print("开始工作")
    time.sleep(5)
    print("工作完成")

t = threading.Thread(target=work)
t.start()

print("主线程继续")

t.join()

print("程序结束")