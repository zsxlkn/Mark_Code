import httpx
import json
from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse

app = FastAPI()

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


@app.post("/v1/messages")
async def proxy(request: Request):

    body = await request.json()

    # ===== 转 OpenAI格式 =====
    payload = {
        "model": "deepseek-chat",
        "messages": body["messages"],
        "stream": True
    }

    headers = {
        "Authorization": request.headers.get("authorization"),
        "Content-Type": "application/json",
    }

    async def stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                DEEPSEEK_URL,
                json=payload,
                headers=headers,
            ) as resp:

                # ===== Anthropic 协议开始 =====
                yield "event: message_start\n"
                yield "data: {}\n\n"

                yield "event: content_block_start\n"
                yield "data: {\"index\":0,\"content_block\":{\"type\":\"text\",\"text\":\"\"}}\n\n"

                buffer_text = ""

                async for line in resp.aiter_lines():

                    if not line:
                        continue

                    if "data:" not in line:
                        continue

                    raw = line.replace("data: ", "")

                    try:
                        data = json.loads(raw)

                        delta = data["choices"][0]["delta"].get("content", "")
                        if delta:

                            buffer_text += delta

                            # ===== Anthropic content delta =====
                            yield "event: content_block_delta\n"
                            yield "data: " + json.dumps({
                                "index": 0,
                                "delta": {
                                    "type": "text",
                                    "text": delta
                                }
                            }, ensure_ascii=False) + "\n\n"

                    except:
                        continue

                # ===== block stop =====
                yield "event: content_block_stop\n"
                yield "data: {\"index\":0}\n\n"

                # ===== message delta =====
                yield "event: message_delta\n"
                yield "data: {\"stop_reason\":\"end_turn\"}\n\n"

                # ===== message end =====
                yield "event: message_stop\n"
                yield "data: {}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream"
    )
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)