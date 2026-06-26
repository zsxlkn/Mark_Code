"""
Claude Code → DeepSeek 代理服务器 (v2 - 修复SSE格式)

关键修复:
  - Anthropic SSE 必须同时包含 "event: <name>" 和 "data: {...}" 两行
  - 之前只发了 data: 行，Claude Code 解析不出来报 "empty or malformed response"
"""

import json
import uuid
import httpx
from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse, JSONResponse

app = FastAPI(title="Claude Code → DeepSeek Proxy v2")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

MODEL_MAP = {
    "deepseek-v4-pro":           "deepseek-chat",
    "deepseek-v4-pro[1m]":       "deepseek-chat",
    "deepseek-v4-flash":         "deepseek-chat",
    "claude-3-5-sonnet-20241022":"deepseek-chat",
    "claude-opus-4-5":           "deepseek-chat",
}
DEFAULT_MODEL = "deepseek-chat"


class AppLogger:
    def __init__(self, log_file="llm.log"):
        self.log_file = log_file
        open(self.log_file, "w", encoding="utf-8").close()

    def log(self, msg):
        line = str(msg)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line)


logger = AppLogger()


# ── 格式转换 ──────────────────────────────────────────

def anthropic_to_openai_messages(anthropic_body: dict) -> list:
    """Anthropic messages → OpenAI messages"""
    messages = []

    # system prompt (Anthropic放在顶层字段)
    system = anthropic_body.get("system")
    if system:
        if isinstance(system, str):
            messages.append({"role": "system", "content": system})
        elif isinstance(system, list):
            text = "\n".join(
                b.get("text", "") for b in system if b.get("type") == "text"
            )
            if text:
                messages.append({"role": "system", "content": text})

    # 对话消息
    for msg in anthropic_body.get("messages", []):
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            parts = []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    parts.append(block.get("text", ""))
                elif btype == "tool_result":
                    # 把 tool_result 也转成文本
                    tr_content = block.get("content", "")
                    if isinstance(tr_content, list):
                        for c in tr_content:
                            if c.get("type") == "text":
                                parts.append(c.get("text", ""))
                    elif isinstance(tr_content, str):
                        parts.append(tr_content)
            merged = "\n".join(p for p in parts if p)
            if merged:
                messages.append({"role": role, "content": merged})

    return messages


# ── SSE 事件构造器 (关键：必须有 event: 行) ──────────

def sse(event_name: str, data: dict) -> str:
    """生成符合 Anthropic 规范的 SSE 事件"""
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def event_message_start(msg_id: str, model: str) -> str:
    return sse("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    })


def event_content_block_start() -> str:
    return sse("content_block_start", {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    })


def event_ping() -> str:
    return sse("ping", {"type": "ping"})


def event_content_block_delta(text: str) -> str:
    return sse("content_block_delta", {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "text_delta", "text": text},
    })


def event_content_block_stop() -> str:
    return sse("content_block_stop", {
        "type": "content_block_stop",
        "index": 0,
    })


def event_message_delta(stop_reason: str, output_tokens: int) -> str:
    return sse("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"output_tokens": output_tokens},
    })


def event_message_stop() -> str:
    return sse("message_stop", {"type": "message_stop"})


# ── 主路由 ────────────────────────────────────────────

@app.post("/v1/messages")
async def proxy_messages(request: Request):
    body = await request.json()

    requested_model = body.get("model", "")
    deepseek_model = MODEL_MAP.get(requested_model, DEFAULT_MODEL)
    openai_messages = anthropic_to_openai_messages(body)
    stream = body.get("stream", True)

    logger.log(f"\n===== REQUEST (model={requested_model} → {deepseek_model}, stream={stream}, msgs={len(openai_messages)}) =====")

    payload = {
        "model": deepseek_model,
        "messages": openai_messages,
        "stream": True,
        "max_tokens": body.get("max_tokens", 8192),
    }
    if body.get("temperature") is not None:
        payload["temperature"] = body["temperature"]

    auth_header = request.headers.get("authorization", "")
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    # ── 流式 ──────────────────────────────────────────
    if stream:
        async def event_stream():
            # 1. message_start
            yield event_message_start(msg_id, requested_model)
            # 2. content_block_start
            yield event_content_block_start()
            # 3. ping
            yield event_ping()

            output_tokens = 0
            stop_reason = "end_turn"

            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST", DEEPSEEK_URL,
                        json=payload,
                        headers={
                            "Authorization": auth_header,
                            "Content-Type": "application/json",
                        },
                    ) as resp:
                        logger.log(f"DeepSeek STATUS: {resp.status_code}")

                        if resp.status_code != 200:
                            err_text = await resp.aread()
                            logger.log(f"DeepSeek ERROR BODY: {err_text}")
                            yield event_content_block_delta(f"[DeepSeek error {resp.status_code}]")
                        else:
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data:"):
                                    continue
                                raw = line[5:].strip()
                                if raw == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(raw)
                                except json.JSONDecodeError:
                                    continue

                                if chunk.get("usage"):
                                    output_tokens = chunk["usage"].get("completion_tokens", 0)

                                choices = chunk.get("choices", [])
                                if not choices:
                                    continue

                                delta = choices[0].get("delta", {})
                                text = delta.get("content", "")
                                finish = choices[0].get("finish_reason")

                                if text:
                                    logger.log(f"[Δ] {repr(text)}")
                                    yield event_content_block_delta(text)

                                if finish == "length":
                                    stop_reason = "max_tokens"

            except Exception as e:
                logger.log(f"EXCEPTION: {e}")
                yield event_content_block_delta(f"[proxy error: {e}]")

            # 4. content_block_stop
            yield event_content_block_stop()
            # 5. message_delta (含 stop_reason + usage)
            yield event_message_delta(stop_reason, output_tokens)
            # 6. message_stop
            yield event_message_stop()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",   # 关掉nginx/代理的缓冲
            },
        )

    # ── 非流式 ────────────────────────────────────────
    else:
        collected = []
        usage_data = None
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST", DEEPSEEK_URL,
                    json=payload,
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/json",
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            chunk = json.loads(raw)
                            if chunk.get("usage"):
                                usage_data = chunk["usage"]
                            choices = chunk.get("choices", [])
                            if choices:
                                text = choices[0].get("delta", {}).get("content", "")
                                if text:
                                    collected.append(text)
                        except Exception:
                            pass
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

        full_text = "".join(collected)
        logger.log(f"[non-stream] {repr(full_text)}")

        return JSONResponse({
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": full_text}],
            "model": requested_model,
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": (usage_data or {}).get("prompt_tokens", 0),
                "output_tokens": (usage_data or {}).get("completion_tokens", 0),
            },
        })


# ── token 计数端点 (Claude Code 偶尔会调用) ───────────

@app.post("/v1/messages/count_tokens")
async def count_tokens(request: Request):
    body = await request.json()
    # 粗略估算: 字符数 / 3
    total = 0
    for msg in body.get("messages", []):
        c = msg.get("content", "")
        if isinstance(c, str):
            total += len(c)
        elif isinstance(c, list):
            for b in c:
                if b.get("type") == "text":
                    total += len(b.get("text", ""))
    return JSONResponse({"input_tokens": total // 3})


@app.get("/")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Claude Code → DeepSeek 代理 v2 启动: http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
