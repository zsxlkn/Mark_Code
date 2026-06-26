import asyncio
import time


def sync_task(name, delay):
    print(f"{name} 开始...")
    time.sleep(delay)  # 阻塞！整个程序卡在这里
    print(f"{name} 完成！")
    return f"{name} 结果"

# 串行执行，总共需要 1+2+3 = 6 秒
start = time.time()
sync_task("任务A", 1)
sync_task("任务B", 2)
sync_task("任务C", 3)
print(f"总耗时: {time.time() - start:.6f}秒")

print("=" * 50)


async def async_task(name, delay):
    print(f"{name} 开始...")
    await asyncio.sleep(delay)  # 非阻塞！让出控制权
    print(f"{name} 完成！")
    return f"{name} 结果"

async def main():
    # 并发执行三个任务，总共只需要约 3 秒（最慢的那个）
    tasks = [
        async_task("任务A", 1),
        async_task("任务B", 2),
        async_task("任务C", 3)
    ]
    results = await asyncio.gather(*tasks)  # 同时等待所有任务
    print(f"结果: {results}")

# 运行异步主函数
start = time.time()
asyncio.run(main())
print(f"总耗时: {time.time() - start:.2f}秒")


async def A():
    print("A开始")
    await asyncio.sleep(5)
    #  time.sleep(5)          # 故意阻塞整个线程
    print("A结束")

async def B():
    for i in range(5):
        print("B", i)
        await asyncio.sleep(1)

async def main():
    await asyncio.gather(A(), B())

asyncio.run(main())
