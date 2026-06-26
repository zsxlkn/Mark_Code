def hello():
    print("hahahahah")
# hello 是一个函数对象
print("hello is ",hello)
f = hello
print("f is ",hello)
f()

def logger(func):

    def wrapper():
        print("开始")
        func()
        print("结束")

    return wrapper

@logger
def hello():
    print("hahahahah")

print(hello)

def logger(func):
    print("进入logger")

    def wrapper():
        print("before")
        func()
        print("after")

    return wrapper

@logger
def hello():
    print("Hello")

hello()
hello()
hello()
