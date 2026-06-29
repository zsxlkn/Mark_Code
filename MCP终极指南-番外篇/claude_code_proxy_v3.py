"""
Claude Code → DeepSeek 代理服务器 (v3 - 完整对话日志)

v3 新增:
  - 完整记录每个请求的 system prompt (含 MCP servers / tools 描述)
  - 完整记录 tools 定义列表
  - 完整记录 messages 历史
  - 聚合完整的模型响应文本 (不再只是零散chunks)
  - 漂亮的分隔符 + 时间戳，方便阅读
  - 日志文件 + 控制台同步输出
"""

import json
import uuid
import time
import datetime
import httpx
from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse, JSONResponse

app = FastAPI(title="Claude Code → DeepSeek Proxy v3")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

MODEL_MAP = {
    "deepseek-v4-pro":           "deepseek-chat",
    "deepseek-v4-pro[1m]":       "deepseek-chat",
    "deepseek-v4-flash":         "deepseek-chat",
    "claude-3-5-sonnet-20241022":"deepseek-chat",
    "claude-opus-4-5":           "deepseek-chat",
    "claude-opus-4-8":           "deepseek-chat",
}
DEFAULT_MODEL = "deepseek-chat"


# ═══════════════════════════════════════════════════════════════
#  日志系统
# ═══════════════════════════════════════════════════════════════

class ConversationLogger:
    """对话级别的日志记录器：把每次完整的请求/响应作为一个'回合'记录"""

    def __init__(self, log_file="llm.log"):
        self.log_file = log_file
        # 启动时清空 (改成 "a" 就是追加模式)，启动时用 "w" 模式打开然后立即关闭，这是清空文件的惯用写法。
        open(self.log_file, "w", encoding="utf-8").close()
        self.turn = 0 # self.turn 用来给每个回合编号。

    def _write(self, text: str):
        # _write 同时写文件和控制台
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        print(text)

    def _hr(self, char="═", width=80):
        return char * width

    def _section(self, title: str, char="─", width=80):
        pad = (width - len(title) - 2) // 2
        return f"{char * pad} {title} {char * (width - pad - len(title) - 2)}"

    def log_request(self, body: dict, requested_model: str, deepseek_model: str):
        """记录一个完整的请求"""
        """
        body — Claude Code 发过来的完整请求体（原始 JSON，一个 Python dict）

        lines = [] 是核心设计决策。整个函数不直接一行一行写文件，而是先把所有内容收集到 lines 列表里，
        最后一次性调用 self._write("\n".join(lines)) 写入。
        好处是：文件写入是一个原子操作，不会出现两个并发请求的日志行互相穿插的情况。
        """
        self.turn += 1
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = []
        lines.append("")
        lines.append(self._hr("═"))
        lines.append(f"║ TURN #{self.turn}  |  {ts}  |  {requested_model} → {deepseek_model}")
        lines.append(self._hr("═"))

        # ── 顶层参数 ──
        lines.append(self._section("REQUEST META"))
        # body 是完整的请求，但 messages、system、tools、tool_choice 这四个字段内容巨大，
        # 后面各有专门区段处理。这里用字典推导式把它们过滤掉，只留下轻量的元数据字段
        meta = {k: v for k, v in body.items()
                if k not in ("messages", "system", "tools", "tool_choice")}
        lines.append(json.dumps(meta, ensure_ascii=False, indent=2)) # json.dumps 在这里的作用是将 Python 对象（这里是字符串 char）转换成 JSON 格式的字符串,让中文直接以 UTF-8 输出

        # ── System Prompt (含 MCP / 环境信息) ──
        system = body.get("system")
        if system:
            lines.append("")
            lines.append(self._section("SYSTEM PROMPT"))
            if isinstance(system, str):
                lines.append(system)
            elif isinstance(system, list):
                for i, block in enumerate(system):
                    if block.get("type") == "text":
                        cache_tag = " [cached]" if block.get("cache_control") else ""
                        lines.append(f"--- system block #{i}{cache_tag} ---")
                        lines.append(block.get("text", ""))

        # ── Tools (Claude Code 暴露的所有工具，含 MCP server tools) ──
        tools = body.get("tools")
        if tools:
            lines.append("")
            lines.append(self._section(f"TOOLS AVAILABLE ({len(tools)})"))
            for t in tools:
                name = t.get("name", "?")
                desc = t.get("description", "")
                # 截断超长描述，但保留前面 300 字
                short_desc = desc.replace("\n", " ").strip()
                if len(short_desc) > 300:
                    short_desc = short_desc[:300] + "..."
                lines.append(f"  • {name}")
                if short_desc:
                    lines.append(f"      {short_desc}")
                # 输入参数 schema
                schema = t.get("input_schema", {})
                props = schema.get("properties", {})
                if props:
                    param_names = ", ".join(props.keys())
                    lines.append(f"      params: {param_names}")
            lines.append("")
            lines.append(self._section("TOOLS FULL JSON", char="·"))
            lines.append(json.dumps(tools, ensure_ascii=False, indent=2))

        # ── tool_choice ──
        if body.get("tool_choice"):
            lines.append("")
            lines.append(self._section("TOOL CHOICE"))
            lines.append(json.dumps(body["tool_choice"], ensure_ascii=False, indent=2))

        # ── Messages 历史 ──
        messages = body.get("messages", [])
        lines.append("")
        lines.append(self._section(f"MESSAGES ({len(messages)})"))
        for i, msg in enumerate(messages):
            role = msg["role"].upper()
            lines.append(f"┌─[{i}] {role} " + "─" * max(0, 70 - len(role)))
            content = msg["content"]
            if isinstance(content, str):
                for ln in content.splitlines() or [""]:
                    lines.append(f"│ {ln}")
            elif isinstance(content, list):
                for j, block in enumerate(content):
                    btype = block.get("type", "?")
                    lines.append(f"│ ◇ block[{j}] type={btype}")
                    if btype == "text":
                        for ln in block.get("text", "").splitlines():
                            lines.append(f"│   {ln}")
                    elif btype == "tool_use":
                        lines.append(f"│   tool_name = {block.get('name')}")
                        lines.append(f"│   tool_id   = {block.get('id')}")
                        inp = block.get("input", {})
                        for ln in json.dumps(inp, ensure_ascii=False, indent=2).splitlines():
                            lines.append(f"│   {ln}")
                    elif btype == "tool_result":
                        lines.append(f"│   tool_use_id = {block.get('tool_use_id')}")
                        tc = block.get("content", "")
                        if isinstance(tc, str):
                            for ln in tc.splitlines():
                                lines.append(f"│   {ln}")
                        elif isinstance(tc, list):
                            for c in tc:
                                if c.get("type") == "text":
                                    for ln in c.get("text", "").splitlines():
                                        lines.append(f"│   {ln}")
                    else:
                        for ln in json.dumps(block, ensure_ascii=False, indent=2).splitlines():
                            lines.append(f"│   {ln}")
            lines.append("└" + "─" * 79)

        lines.append("")
        self._write("\n".join(lines))

    def log_response(self, full_text: str, usage, stop_reason: str, duration: float):
        """记录一个完整的响应"""
        lines = []
        lines.append(self._section("◀ MODEL RESPONSE", char="━"))

        if full_text:
            for ln in full_text.splitlines():
                lines.append(f"  {ln}")
        else:
            lines.append("  (empty)")

        lines.append("")
        lines.append(self._section("RESPONSE META", char="·"))
        meta = {
            "stop_reason": stop_reason,
            "duration_sec": round(duration, 2),
            "usage": usage or {},
        }
        lines.append(json.dumps(meta, ensure_ascii=False, indent=2))
        lines.append(self._hr("═"))
        lines.append("")

        self._write("\n".join(lines))

    def log_error(self, msg: str):
        self._write(f"\n[ERROR @ {datetime.datetime.now():%H:%M:%S}] {msg}\n")

    def log_info(self, msg: str):
        self._write(f"[INFO @ {datetime.datetime.now():%H:%M:%S}] {msg}")


logger = ConversationLogger()


# ═══════════════════════════════════════════════════════════════
#  格式转换
# ═══════════════════════════════════════════════════════════════

def anthropic_to_openai_messages(anthropic_body: dict) -> list:
    """Anthropic messages → OpenAI messages"""
    messages = []

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
                elif btype == "tool_use":
                    parts.append(
                        f"[Called tool {block.get('name')} with input "
                        f"{json.dumps(block.get('input', {}), ensure_ascii=False)}]"
                    )
                elif btype == "tool_result":
                    tc = block.get("content", "")
                    if isinstance(tc, list):
                        for c in tc:
                            if c.get("type") == "text":
                                parts.append(f"[Tool result] {c.get('text', '')}")
                    elif isinstance(tc, str):
                        parts.append(f"[Tool result] {tc}")
            merged = "\n".join(p for p in parts if p)
            if merged:
                messages.append({"role": role, "content": merged})

    return messages


# ═══════════════════════════════════════════════════════════════
#  SSE 事件构造器
# ═══════════════════════════════════════════════════════════════

def sse(event_name: str, data: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def evt_message_start(msg_id: str, model: str) -> str:
    return sse("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id, "type": "message", "role": "assistant",
            "content": [], "model": model,
            "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    })

def evt_content_block_start() -> str:
    return sse("content_block_start", {
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "text", "text": ""},
    })

def evt_ping() -> str:
    return sse("ping", {"type": "ping"})

def evt_content_block_delta(text: str) -> str:
    return sse("content_block_delta", {
        "type": "content_block_delta", "index": 0,
        "delta": {"type": "text_delta", "text": text},
    })

def evt_content_block_stop() -> str:
    return sse("content_block_stop", {"type": "content_block_stop", "index": 0})

def evt_message_delta(stop_reason: str, output_tokens: int) -> str:
    return sse("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"output_tokens": output_tokens},
    })

def evt_message_stop() -> str:
    return sse("message_stop", {"type": "message_stop"})


# ═══════════════════════════════════════════════════════════════
#  主路由
# ═══════════════════════════════════════════════════════════════

@app.post("/v1/messages")
async def proxy_messages(request: Request):
    body = await request.json()

    requested_model = body.get("model", "")
    deepseek_model = MODEL_MAP.get(requested_model, DEFAULT_MODEL)
    openai_messages = anthropic_to_openai_messages(body)
    stream = body.get("stream", True)

    # ★ 完整记录请求
    logger.log_request(body, requested_model, deepseek_model)

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

    if stream:
        async def event_stream():
            yield evt_message_start(msg_id, requested_model)
            yield evt_content_block_start()
            yield evt_ping()

            output_tokens = 0
            stop_reason = "end_turn"
            usage_data = None
            collected = []
            t0 = time.time()

            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream( "POST", DEEPSEEK_URL, json=payload,headers={"Authorization": auth_header, "Content-Type": "application/json", }, ) as resp:
                        if resp.status_code != 200:
                            err_text = await resp.aread()
                            err_str = err_text.decode("utf-8", errors="replace")
                            logger.log_error(f"DeepSeek HTTP {resp.status_code}: {err_str}")
                            err_msg = f"[DeepSeek error {resp.status_code}: {err_str[:200]}]"
                            collected.append(err_msg)
                            yield evt_content_block_delta(err_msg)
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

                                if chunk.get("usage"): # 最后一个 chunk（带 finish_reason 的那个）
                                    usage_data = chunk["usage"]
                                    output_tokens = usage_data.get("completion_tokens", 0)

                                choices = chunk.get("choices", [])
                                if not choices:
                                    continue

                                delta = choices[0].get("delta", {})
                                text = delta.get("content", "")
                                finish = choices[0].get("finish_reason")

                                if text:
                                    collected.append(text)
                                    yield evt_content_block_delta(text)

                                if finish == "length":
                                    stop_reason = "max_tokens"

            except Exception as e:
                logger.log_error(f"Exception in stream: {e}")
                err_msg = f"[proxy error: {e}]"
                collected.append(err_msg)
                yield evt_content_block_delta(err_msg)

            yield evt_content_block_stop()
            yield evt_message_delta(stop_reason, output_tokens)
            yield evt_message_stop()

            logger.log_response(
                full_text="".join(collected),
                usage=usage_data,
                stop_reason=stop_reason,
                duration=time.time() - t0,
            )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    else:
        collected = []
        usage_data = None
        t0 = time.time()
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
            logger.log_error(f"non-stream error: {e}")
            return JSONResponse(status_code=500, content={"error": str(e)})

        full_text = "".join(collected)
        logger.log_response(full_text, usage_data, "end_turn", time.time() - t0)

        return JSONResponse({
            "id": msg_id, "type": "message", "role": "assistant",
            "content": [{"type": "text", "text": full_text}],
            "model": requested_model,
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {
                "input_tokens": (usage_data or {}).get("prompt_tokens", 0),
                "output_tokens": (usage_data or {}).get("completion_tokens", 0),
            },
        })


@app.post("/v1/messages/count_tokens")
async def count_tokens(request: Request):
    body = await request.json()
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
    print("🚀 Claude Code → DeepSeek 代理 v3 启动: http://127.0.0.1:8000")
    print("📝 日志文件: llm.log")
    uvicorn.run(app, host="0.0.0.0", port=8000)
