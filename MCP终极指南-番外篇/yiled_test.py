def f():
    yield 1
    yield 2

g = f()
print(next(g))  # 1
print(next(g))  # 2

# 每次 yield → 暂停函数,下次 next() → 从暂停处继续
# for x in something: 本质要求 something 是“可迭代对象”,而 yield 会自动把函数变成迭代器（iterator）
for i in f():
    print(i)


def my_range(n):
    i = 0
    while i < n:
        yield i
        i += 1

for x in my_range(10):
    print(x)

# yield 会保存当前执行位置下次从“断点”继续
def gen():
    print("A")
    yield 1
    print("B")
    yield 2
    print("C")

g = gen()
print(next(g))
print(next(g))
