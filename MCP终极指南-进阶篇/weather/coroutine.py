import asyncio
from typing import Any

async def foo():
    print("hahahahah")

#  foo()
print(type(foo))
coro = foo()
print(coro)
asyncio.run(foo())