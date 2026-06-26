try:
    x = 10 / 0

except ValueError:
    print("输入不是整数")
    
except Exception as e:
    print(e)

