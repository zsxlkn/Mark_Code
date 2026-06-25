import threading
import time

def work():
    while True:
        print("working...")
        time.sleep(1)

# t = threading.Thread(target=work,daemon=True)
t = threading.Thread(target=work)
t.start()

print("main exit")
time.sleep(5) # Keep the main thread alive for a while to observe the daemon thread's output