"""
Claude Code → DeepSeek 代理服务器

工作原理:
  Claude Code  →  POST /v1/messages (Anthropic格式)
  本代理       →  POST https://api.deepseek.com/chat/completions (OpenAI格式)
  DeepSeek响应 →  转换回 Anthropic SSE 格式
  Claude Code  ←  Anthropic SSE 流

启动方式:
  pip install fastapi uvicorn httpx
  python claude_code_proxy.py

PowerShell 环境变量:
  $env:ANTHROPIC_BASE_URL="http://127.0.0.1:8000"
  $env:ANTHROPIC_AUTH_TOKEN="sk-你的deepseek-key"
"""

import json
import time
import uuid
import httpx
from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse, JSONResponse

app = FastAPI(title="Claude Code → DeepSeek Proxy")

# ── 配置 ──────────────────────────────────────────────
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# Claude Code 请求的模型名 → DeepSeek 实际模型名
MODEL_MAP = {
    "deepseek-v4-pro":       "deepseek-chat",
    "deepseek-v4-pro[1m]":   "deepseek-chat",   # 中括号版本也能识别
    "deepseek-v4-flash":     "deepseek-chat",
    "claude-3-5-sonnet-20241022": "deepseek-chat",
    "claude-opus-4-5":       "deepseek-chat",
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


# ── 格式转换工具 ──────────────────────────────────────

def anthropic_to_openai_messages(anthropic_body: dict) -> list:
    """把 Anthropic messages 格式转成 OpenAI messages 格式"""
    messages = []

    # system prompt
    system = anthropic_body.get("system")
    if system:
        if isinstance(system, str):
            messages.append({"role": "system", "content": system})
        elif isinstance(system, list):
            # Anthropic system 可以是 content block 列表
            text = " ".join(
                b.get("text", "") for b in system if b.get("type") == "text"
            )
            if text:
                messages.append({"role": "system", "content": text})

    for msg in anthropic_body.get("messages", []):
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            # 把 content blocks 合并成纯文本（工具调用暂不处理）
            parts = []
            for block in content:
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            messages.append({"role": role, "content": "\n".join(parts)})
        else:
            messages.append({"role": role, "content": str(content)})

    return messages


def make_anthropic_chunk(text: str, msg_id: str, model: str) -> str:
    """生成 Anthropic content_block_delta SSE chunk"""
    data = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "text_delta", "text": text},
    }
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def make_anthropic_start(msg_id: str, model: str) -> list[str]:
    """流开始时的 Anthropic SSE 事件序列"""
    events = []

    # message_start
    events.append("data: " + json.dumps({
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
        }
    }) + "\n\n")

    # content_block_start
    events.append("data: " + json.dumps({
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    }) + "\n\n")

    # ping
    events.append("data: " + json.dumps({"type": "ping"}) + "\n\n")

    return events


def make_anthropic_end(msg_id: str, stop_reason: str = "end_turn",
                       usage: dict | None = None) -> list[str]:
    """流结束时的 Anthropic SSE 事件序列"""
    events = []

    events.append("data: " + json.dumps({
        "type": "content_block_stop",
        "index": 0,
    }) + "\n\n")

    events.append("data: " + json.dumps({
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"output_tokens": (usage or {}).get("completion_tokens", 0)},
    }) + "\n\n")

    events.append("data: " + json.dumps({
        "type": "message_stop",
    }) + "\n\n")

    return events


# ── 主路由：/v1/messages ──────────────────────────────

@app.post("/v1/messages")
async def proxy_messages(request: Request):
    body = await request.json()
    logger.log(f"\n===== CLAUDE CODE REQUEST =====\n{json.dumps(body, ensure_ascii=False, indent=2)}")

    # 解析模型名（兼容中括号写法）
    requested_model = body.get("model", "")
    deepseek_model = MODEL_MAP.get(requested_model, DEFAULT_MODEL)

    # 转换消息格式
    openai_messages = anthropic_to_openai_messages(body)

    # 是否流式
    stream = body.get("stream", True)

    payload = {
        "model": deepseek_model,
        "messages": openai_messages,
        "stream": True,   # 始终用流式，统一处理
        "max_tokens": body.get("max_tokens", 8192),
    }

    if body.get("temperature") is not None:
        payload["temperature"] = body["temperature"]

    auth_header = request.headers.get("authorization", "")
    logger.log(f"→ DeepSeek model: {deepseek_model}, stream={stream}")
    logger.log(f"→ Messages count: {len(openai_messages)}")

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    # ── 流式响应 ──────────────────────────────────────
    if stream:
        async def event_stream():
            # 发送 Anthropic 流开始事件
            for evt in make_anthropic_start(msg_id, requested_model):
                yield evt

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
                        logger.log(f"DeepSeek STATUS: {resp.status_code}")

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

                            # 提取 usage
                            if chunk.get("usage"):
                                usage_data = chunk["usage"]

                            choices = chunk.get("choices", [])
                            if not choices:
                                continue

                            delta = choices[0].get("delta", {})
                            text = delta.get("content", "")
                            finish = choices[0].get("finish_reason")

                            if text:
                                logger.log(f"[chunk] {repr(text)}")
                                yield make_anthropic_chunk(text, msg_id, requested_model)

            except Exception as e:
                logger.log(f"ERROR: {e}")
                yield "data: " + json.dumps({"type": "error", "error": {"type": "api_error", "message": str(e)}}) + "\n\n"

            # 发送 Anthropic 流结束事件
            for evt in make_anthropic_end(msg_id, usage=usage_data):
                yield evt

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # ── 非流式响应（Claude Code 有时用 stream=false） ──
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
            logger.log(f"ERROR (non-stream): {e}")
            return JSONResponse(status_code=500, content={"error": str(e)})

        full_text = "".join(collected)
        logger.log(f"[non-stream response] {repr(full_text)}")

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


# ── 健康检查 ──────────────────────────────────────────

@app.get("/")
async def health():
    return {"status": "ok", "proxy": "Claude Code → DeepSeek"}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Claude Code → DeepSeek 代理启动在 http://127.0.0.1:8000")
    print("📋 PowerShell 环境变量设置:")
    print('   $env:ANTHROPIC_BASE_URL="http://127.0.0.1:8000"')
    print('   $env:ANTHROPIC_AUTH_TOKEN="sk-你的deepseek-key"')
    uvicorn.run(app, host="0.0.0.0", port=8000)
