import httpx

resp = httpx.get("https://api.github.com/users/octocat", timeout=30.0)
# resp = httpx.get("https://www.baidu.com")
print(resp.text)
