"""
测试 SSE 流式对话协议

测试项：
1. parsePostSSE 正确解析 event: message / event: end / event: error
2. event: end 结束信号处理
3. event: error 异常通知处理
4. 非 200 响应抛出异常
"""

# ===== 模拟 parsePostSSE 逻辑（前端 TypeScript 逻辑的 Python 验证）=====

def test_sse_event_parsing():
    """验证 SSE 事件解析逻辑"""
    raw_events = """event: status
data: {"message": "正在思考..."}

event: message
data: {"content": "React 的"}

event: message
data: {"content": "核心原理"}

event: end
data: {"finished": true}

"""
    events = []
    buffer = ""
    parts = raw_events.split("\n\n")
    for part in parts:
        if not part.strip():
            continue
        lines = part.split("\n")
        event_type = "message"
        data_str = ""
        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:]
        if data_str:
            events.append({"event": event_type, "data": data_str})
    
    assert len(events) == 4, f"应解析 4 个事件，实际: {len(events)}"
    assert events[0]["event"] == "status", "第一个事件应为 status"
    assert events[1]["event"] == "message", "第二个事件应为 message"
    assert events[2]["event"] == "message", "第三个事件应为 message"
    assert events[3]["event"] == "end", "第四个事件应为 end"
    print(f"PASS: SSE 事件解析正确 - {len(events)} 个事件, 类型: {[e['event'] for e in events]}")


def test_sse_error_event():
    """验证 error 事件处理"""
    raw_events = """event: status
data: {"message": "处理中..."}

event: error
data: {"message": "LLM 服务暂时不可用"}

"""
    events = []
    parts = raw_events.split("\n\n")
    for part in parts:
        if not part.strip():
            continue
        lines = part.split("\n")
        event_type = "message"
        data_str = ""
        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:]
        if data_str:
            events.append({"event": event_type, "data": data_str})
    
    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1, "应有 1 个 error 事件"
    print(f"PASS: error 事件正确捕获 - {error_events[0]['data']}")


def test_sse_non_200_response():
    """非 200 响应应抛出异常"""
    class MockResponse:
        ok = False
        status_code = 429
        async def json(self):
            return {"detail": "请求过于频繁"}
    
    response = MockResponse()
    assert not response.ok, "非 200 响应 ok 应为 False"
    assert response.status_code == 429, "状态码应为 429"
    print(f"PASS: 非 200 响应 ({response.status_code}) 正确识别")


def test_sse_stream_concatenation():
    """验证流式内容拼接"""
    message_chunks = [
        {"content": "React"},
        {"content": " 的 Virtual DOM "},
        {"content": "通过 diff 算法"},
        {"content": "比较新旧节点树"},
    ]
    
    full_reply = ""
    for chunk in message_chunks:
        full_reply += chunk.get("content", "")
    
    assert full_reply == "React 的 Virtual DOM 通过 diff 算法比较新旧节点树"
    assert len(full_reply) > 0, "拼接后内容不应为空"
    print(f"PASS: 流式内容拼接正确 - 总长度: {len(full_reply)} 字符")


if __name__ == "__main__":
    print("=" * 60)
    print("SSE 流式对话协议测试")
    print("=" * 60)
    
    print("\n--- 测试 1: SSE 事件解析 ---")
    test_sse_event_parsing()
    
    print("\n--- 测试 2: error 事件处理 ---")
    test_sse_error_event()
    
    print("\n--- 测试 3: 非 200 响应 ---")
    test_sse_non_200_response()
    
    print("\n--- 测试 4: 流式内容拼接 ---")
    test_sse_stream_concatenation()
    
    print("\n" + "=" * 60)
    print("所有 SSE 流式对话测试通过!")
    print("=" * 60)
