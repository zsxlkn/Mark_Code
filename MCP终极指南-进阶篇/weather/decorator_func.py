# 1. 定义一个装饰器函数
def logger(func):
    """这是一个装饰器，给函数增加日志功能"""
    
    def wrapper(*args, **kwargs):
        # 在调用原函数之前做的事
        print(f"调用 {func.__name__}，参数: {args}, {kwargs}")
        
        # 调用原函数
        result = func(*args, **kwargs)
        
        # 在调用原函数之后做的事
        print(f"{func.__name__} 返回: {result}")
        
        return result
    
    return wrapper

# 2. 使用装饰器（手动方式）
def add(a, b):
    return a + b

@logger  # 等价于 multiply = logger(multiply)
def multiply(a, b):
    return a * b

# 相当于：add = logger(add)  # 把原函数传给装饰器，返回新函数
add = logger(add)

# 3. 调用时，实际执行的是 wrapper
add(3, 5)

multiply(2, 4)  # 自动带日志

print("=" * 100)

import time

def timer(func):
    """计算函数执行时间"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} 执行耗时: {end - start:.4f}秒")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)
    return "完成"

slow_function()  # 输出: slow_function 执行耗时: 1.0002秒


print("=" * 100)
def retry(max_retries=3, delay=1):
    """失败时自动重试"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise  # 最后一次失败，抛出异常
                    print(f"重试 {attempt + 1}/{max_retries}，错误: {e}")
                    time.sleep(delay)
        return wrapper
    return decorator

@retry(max_retries=3, delay=0.5)
def unstable_request():
    import random
    if random.random() < 0.1:  # 10%概率失败
        raise Exception("网络错误")
    return "成功！"

# 测试
print(unstable_request)
print(unstable_request())

print("="*100)

def require_login(func):
    """检查用户是否登录"""
    def wrapper(*args, **kwargs):
        if not args[0].get('is_logged_in', False):
            return "请先登录！"
        return func(*args, **kwargs)
    return wrapper

@require_login
def view_profile(user):
    return f"用户 {user['name']} 的个人资料"

# 测试
guest = {'name': '访客', 'is_logged_in': False}
admin = {'name': '张三', 'is_logged_in': True}

print(view_profile(guest))  # 输出: 请先登录！
print(view_profile(admin))  # 输出: 用户 张三 的个人资料



print("=" * 100)
from functools import wraps
def my_decorator(func):
    @wraps(func)  # 这行很重要！保留原函数的名称和文档
    def wrapper(*args, **kwargs):
        """这是wrapper的文档"""
        return func(*args, **kwargs)
    return wrapper

@my_decorator
def my_function():
    """这是原函数的文档"""
    pass

print(my_function.__name__)  # 输出: my_function（没有@wraps会输出wrapper）
print(my_function.__doc__)   # 输出: 这是原函数的文档

print("=" * 100)
def my_wraps(original_func):
    """手动实现wraps的功能"""
    def decorator(wrapper_func):
        # 把原函数的元信息复制到包装函数上
        wrapper_func.__name__ = original_func.__name__
        wrapper_func.__doc__ = original_func.__doc__
        wrapper_func.__annotations__ = original_func.__annotations__
        wrapper_func.__module__ = original_func.__module__
        # 还有更多属性...
        return wrapper_func
    return decorator

# 使用手动实现的wraps
def my_decorator(func):

    @my_wraps(func)  # 复制元信息
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    

    return wrapper

@my_decorator
def add(a, b):
    """计算两个数的和"""
    return a + b

print(add.__name__)  # 输出: add ✅
print(add.__doc__)   # 输出: 计算两个数的和 ✅