class Person:
    def __init__(self, name):
        self.name = name
        self.age = 18

print(__file__)  # 输出当前文件的路径
p = Person("Alice")
print(p.__dict__)  
# 输出：{'name': 'Alice', 'age': 18}

# 你甚至可以动态添加属性
p.gender = 'female'
print(p.__dict__)  
# 输出：{'name': 'Alice', 'age': 18, 'gender': 'female'}