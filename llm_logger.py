import httpx
from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse

app = FastAPI(title="LLM API Logger")

class AppLogger:
    def __init__(self, log_file="llm.log"):
        self.log_file = log_file
        open(self.log_file, "w").close()

    def log(self, msg):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")
        print(msg)

logger = AppLogger()

# ✅ 改成 DeepSeek 正确 endpoint
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


@app.post("/chat/completions")
async def proxy_request(request: Request):

    body = await request.json()
    logger.log(f"\n===== REQUEST =====\n{body}")

    # ✅ 强制 OpenAI格式
    payload = {
        "model": "deepseek-chat",
        "messages": body["messages"],
        "stream": True   # ⚠️ 打开 stream（关键）
    }

    async def event_stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                DEEPSEEK_URL,
                json=payload,
                headers={
                    "Authorization": request.headers.get("authorization"),
                    "Content-Type": "application/json",
                },
            ) as response:

                logger.log(f"STATUS: {response.status_code}")

                # ⚠️ DeepSeek是 OpenAI stream格式
                async for line in response.aiter_lines():

                    if not line:
                        continue

                    logger.log(line)

                    # OpenAI SSE → Claude SSE 透传
                    yield f"{line}\n"

                yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)