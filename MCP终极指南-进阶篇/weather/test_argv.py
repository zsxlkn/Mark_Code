import sys

print("=" * 50)
print(f"sys.argv = {sys.argv}")
print(f"sys.argv[0] = {sys.argv[0]}")
print(f"参数个数 = {len(sys.argv)}")

for i, arg in enumerate(sys.argv):
    print(f"  sys.argv[{i}] = {arg}")
print("=" * 50)