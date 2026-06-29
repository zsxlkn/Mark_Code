import asyncio
import json
from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse

app = FastAPI()

@app.get("/")
async def index():
    return {"message": "服务器运行中 🚀", "endpoints": ["/chat", "/stream"]}

@app.get("/zsx")
async def index():
    return {"message": "服务器运行中 🚀,现在是张诗贤的首页", "endpoints": ["/chat", "/stream"],}

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_msg = body.get("message", "")
    reply = f"你说了：「{user_msg}」，我收到了！"
    return {"role": "assistant", "content": reply}

@app.post("/stream")
async def stream_chat(request: Request):
    body = await request.json()
    user_msg = body.get("message", "")
    fake_reply = f"收到你的消息「{user_msg}」！这是流式回复，每个字会逐步出现，就像大模型在思考一样..."

    async def event_stream():
        yield "event: message_start\n"
        yield 'data: {"status": "started"}\n\n'

        # 按【单个字符】拆分，延迟调大到 0.08s，效果明显
        for char in fake_reply:
            await asyncio.sleep(0.15)
            payload = json.dumps({"delta": char}, ensure_ascii=False)
            yield f"event: token\n"
            yield f"data: {payload}\n"

        yield "event: message_stop\n"
        yield 'data: {"status": "done"}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
