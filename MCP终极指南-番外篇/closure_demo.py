import asyncio

def outer():
    x = 10
    def inner():
        print(x)   # inner 引用了 outer 的 x
    return inner   # 把 inner 函数本身返回出去

fn = outer()   # outer 执行完了，但 x 没有消失
fn()           # 输出 10，x 还活着！

"""
Python 闭包 Demo
直接运行: python closure_demo.py
"""

# ═══════════════════════════════════════════════════════
# 例1：最简单的闭包
#      理解"内层函数记住外层变量"
# ═══════════════════════════════════════════════════════

def make_greeter(name):
    """外层函数，接收一个 name"""
    def greet():
        """内层函数，引用了外层的 name"""
        print(f"你好，{name}！")
    return greet   # 返回函数本身，不是调用它

print("=" * 50)
print("例1：最简单的闭包")
print("=" * 50)

greet_alice = make_greeter("Alice")   # make_greeter 执行完毕
greet_bob   = make_greeter("Bob")

greet_alice()   # 输出: 你好，Alice！（name 还活着）
greet_bob()     # 输出: 你好，Bob！

# 关键：两个闭包各自记住了自己的 name，互不干扰
print(f"greet_alice 记住的变量: {greet_alice.__code__.co_freevars}")
print(f"实际的值:               {greet_alice.__closure__[0].cell_contents}")


# ═══════════════════════════════════════════════════════
# 例2：闭包作为"计数器工厂"
#      理解"每次调用外层函数，都创建独立的闭包"
# ═══════════════════════════════════════════════════════

def make_counter(start=0):
    count = start         # 外层变量，会被内层函数"捕获"

    def increment():
        nonlocal count    # 声明要修改外层变量（不加这行只能读不能写）
        count += 1
        return count

    def reset():
        nonlocal count
        count = start

    def get():
        return count

    # 返回多个内层函数，它们共享同一个 count
    return increment, reset, get

print("\n" + "=" * 50)
print("例2：计数器工厂")
print("=" * 50)

inc_a, reset_a, get_a = make_counter(0)
inc_b, reset_b, get_b = make_counter(100)   # 独立的另一个计数器

print(f"计数器A 初始值: {get_a()}")         # 0
print(f"计数器B 初始值: {get_b()}")         # 100

inc_a(); inc_a(); inc_a()
inc_b()

print(f"A +3 后: {get_a()}")               # 3
print(f"B +1 后: {get_b()}")               # 101

reset_a()
print(f"A 重置后: {get_a()}")              # 0
print(f"B 不受影响: {get_b()}")            # 101（两个闭包完全独立）


# ═══════════════════════════════════════════════════════
# 例3：闭包 vs 类
#      闭包可以替代只有一个方法的简单类
# ═══════════════════════════════════════════════════════

# 用类实现"带折扣的价格计算器"
class DiscountCalculatorClass:
    def __init__(self, discount_rate):
        self.discount_rate = discount_rate

    def calculate(self, price):
        return price * (1 - self.discount_rate)

# 用闭包实现同样的功能
def make_discount_calculator(discount_rate):
    def calculate(price):
        return price * (1 - discount_rate)
    return calculate

print("\n" + "=" * 50)
print("例3：闭包 vs 类")
print("=" * 50)

# 类的方式
vip_calc_class = DiscountCalculatorClass(0.2)
print(f"[类] VIP价格 (原价100): {vip_calc_class.calculate(100)}")   # 80.0

# 闭包的方式
vip_calc   = make_discount_calculator(0.2)   # 8折
staff_calc = make_discount_calculator(0.5)   # 5折

print(f"[闭包] VIP价格   (原价100): {vip_calc(100)}")    # 80.0
print(f"[闭包] 员工价格  (原价100): {staff_calc(100)}")  # 50.0

# 闭包更简洁，适合逻辑单一的场景


# ═══════════════════════════════════════════════════════
# 例4：闭包在代理代码中的真实用途
#      模拟 proxy_messages 里 event_stream 的工作方式
# ═══════════════════════════════════════════════════════

def simulate_proxy(request_id, model_name, user_message):
    """
    模拟 proxy_messages：
    外层函数准备好所有参数，内层生成器使用这些参数
    """

    # 这些变量会被内层函数"记住"
    msg_id = f"msg_{request_id:04d}"
    fake_response = f"[{model_name}的回复] 你说的是：'{user_message}'"

    async def stream_generator():
        """内层生成器（闭包），使用外层的 msg_id 和 fake_response"""
        print(f"  [开始] 消息ID={msg_id}")
        # 模拟逐 token 发送
        for char in fake_response:
            await asyncio.sleep(0.15)
            yield char
        print(f"\n  [结束] 消息ID={msg_id}")

    # 外层函数返回后，msg_id 和 fake_response 依然存活
    return stream_generator



async def main():
    gen1 = simulate_proxy(111, "DeepSeek", "中国的首都在哪里")
    gen2 = simulate_proxy(222, "DeepSeek", "Python是什么")
    
    print("请求1 的流式输出:")
    async for token in gen1():  # 使用 async for
        print(token, end="", flush=True)
    
    print("\n\n请求2 的流式输出:")
    async for token in gen2():
        print(token, end="", flush=True)
    print()

print("\n" + "=" * 50)
print("例4：模拟代理中的闭包")
print("=" * 50)
# 运行异步主函数
asyncio.run(main())

# ═══════════════════════════════════════════════════════
# 例5：经典陷阱：循环中创建闭包
#      理解"闭包捕获的是变量本身，不是变量的值"
# ═══════════════════════════════════════════════════════

print("\n" + "=" * 50)
print("例5：经典陷阱与修复")
print("=" * 50)

# ── 错误版本 ──
funcs_wrong = []
for i in range(3):
    def f():
        return i    # 捕获的是变量 i 本身，不是 i 的当前值
    funcs_wrong.append(f)

print("错误版本（期望 0,1,2，实际都是 2）:")
for f in funcs_wrong:
    print(f"  {f()}", end="")   # 输出 2 2 2，因为循环结束后 i=2
print()

# ── 修复方式1：用默认参数把值"固定"进去 ──
funcs_fixed1 = []
for i in range(3):
    def f(x=i):    # 默认参数在函数定义时就求值，把当时的 i 值复制进来
        return x
    funcs_fixed1.append(f)

print("修复方式1 - 默认参数（输出 0,1,2）:")
for f in funcs_fixed1:
    print(f"  {f()}", end="")
print()

# ── 修复方式2：用外层函数包一层，让每次循环有独立的作用域 ──
def make_func(x):
    def f():
        return x   # 每次调用 make_func 都创建新的 x
    return f

funcs_fixed2 = [make_func(i) for i in range(3)]

print("修复方式2 - 工厂函数（输出 0,1,2）:")
for f in funcs_fixed2:
    print(f"  {f()}", end="")
print()


# ═══════════════════════════════════════════════════════
# 总结
# ═══════════════════════════════════════════════════════

print("\n" + "=" * 50)
print("总结")
print("=" * 50)
print("""
闭包的三个要素:
  1. 外层函数定义了变量
  2. 内层函数引用了这些变量
  3. 外层函数返回内层函数

闭包的核心价值:
  • 数据封装：变量藏在闭包里，外部无法直接访问
  • 状态保持：函数执行完，变量依然存活
  • 工厂模式：同一套逻辑，不同的"配置"，生成多个独立函数

nonlocal 关键字:
  • 读外层变量：不需要 nonlocal
  • 写/修改外层变量：必须加 nonlocal，否则 Python 
    会认为你在创建一个新的同名局部变量

经典陷阱:
  • 循环中创建闭包时，捕获的是变量本身，不是值
  • 修复：用默认参数或工厂函数把值"固定"下来
""")
