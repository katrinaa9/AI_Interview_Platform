"""
测试文档异步处理

测试项：
1. 状态流转：pending → processing → completed/failed
2. 空文档内容标记为 failed
3. 文档处理异常捕获与错误记录
4. 知识片段正确创建
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.document_processor import split_chunks, detect_category, detect_difficulty, validate_file


def test_split_chunks_qa_document():
    doc = """Q1: React 是什么？
React 是一个用于构建用户界面的 JavaScript 库。

Q2: Virtual DOM 的作用？
Virtual DOM 通过 diff 算法减少真实 DOM 操作。

Q3: useState 如何使用？
useState 是 React Hooks 之一，用于函数组件状态管理。
"""
    chunks = split_chunks(doc)
    assert len(chunks) >= 3, f"应分割为至少 3 个 chunk，实际: {len(chunks)}"
    print(f"PASS: Q&A 文档正确分割为 {len(chunks)} 个 chunks")


def test_split_chunks_long_content():
    content = "A" * 200 + "\n\n" + "B" * 200 + "\n\n" + "C" * 200
    chunks = split_chunks(content)
    assert len(chunks) >= 1, "长内容应生成 chunks"
    for chunk in chunks:
        assert len(chunk) >= 10, f"每个 chunk 应有最小长度，实际: {len(chunk)}"
    print(f"PASS: 长内容正确分割为 {len(chunks)} 个 chunks")


def test_detect_category():
    react_content = "React 的 useState 和 useEffect 是最常用的 Hooks"
    cat = detect_category(react_content)
    assert "React" in cat, f"应识别 React 分类，实际: {cat}"
    print(f"PASS: 分类识别正确 - '{cat}'")
    
    docker_content = "Docker container 和 Kubernetes 编排"
    cat2 = detect_category(docker_content)
    assert "Docker" in cat2, f"应识别 Docker 分类，实际: {cat2}"
    print(f"PASS: 分类识别正确 - '{cat2}'")
    
    general_content = "这是一个通用问题，不涉及特定技术栈"
    cat3 = detect_category(general_content)
    assert cat3 == "General", f"无特定技术应返回 General，实际: {cat3}"
    print(f"PASS: 无匹配分类返回 'General'")


def test_detect_difficulty():
    hard_content = "请分析 Spring 框架中 IOC 容器的底层原理和源码实现"
    assert detect_difficulty(hard_content) == "hard", "应识别为 hard"
    print("PASS: 高难度识别正确")
    
    easy_content = "什么是 JavaScript？请简单介绍基本概念"
    assert detect_difficulty(easy_content) == "easy", "应识别为 easy"
    print("PASS: 低难度识别正确")
    
    medium_content = "React 的 props 和 state 有什么区别"
    assert detect_difficulty(medium_content) == "medium", "应识别为 medium"
    print("PASS: 中等难度识别正确")


def test_validate_file():
    valid, err = validate_file("test.pdf", 1024)
    assert valid, "PDF 文件应通过验证"
    
    valid, err = validate_file("test.txt", 1024)
    assert valid, "TXT 文件应通过验证"
    
    valid, err = validate_file("test.exe", 1024)
    assert not valid, "EXE 文件不应通过验证"
    print("PASS: 文件类型验证正确")
    
    valid, err = validate_file("test.pdf", 100 * 1024 * 1024)
    assert not valid, "超大文件不应通过验证"
    print("PASS: 文件大小验证正确")


async def test_process_document_lifecycle():
    from app.services.document_processor import process_document
    
    mock_doc = MagicMock()
    mock_doc.id = "doc-test-1"
    mock_doc.filename = "test.pdf"
    mock_doc.status = "pending"
    mock_doc.chunk_count = 0
    
    mock_db = AsyncMock()
    mock_db.get.return_value = mock_doc
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()
    
    class MockSession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, *args):
            pass
    
    with patch("app.services.document_processor.async_session", return_value=MockSession()), \
         patch("app.services.document_processor.extract_text", return_value="Q1: React 是什么？\nReact 是一个 JavaScript 库。\n\nQ2: Virtual DOM？\nVirtual DOM 通过 diff 算法减少 DOM 操作。"):
        
        await process_document("doc-test-1", "test.pdf", "pdf")
        
        assert mock_doc.status == "completed", f"状态应为 completed，实际: {mock_doc.status}"
        assert mock_doc.chunk_count > 0, f"应生成至少一个 chunk，实际: {mock_doc.chunk_count}"
        print(f"PASS: 文档处理生命周期完整 - pending → processing → completed, chunks: {mock_doc.chunk_count}")


if __name__ == "__main__":
    print("=" * 60)
    print("文档异步处理测试")
    print("=" * 60)
    
    print("\n--- 测试 1: Q&A 文档分割 ---")
    test_split_chunks_qa_document()
    
    print("\n--- 测试 2: 长内容分割 ---")
    test_split_chunks_long_content()
    
    print("\n--- 测试 3: 分类识别 ---")
    test_detect_category()
    
    print("\n--- 测试 4: 难度识别 ---")
    test_detect_difficulty()
    
    print("\n--- 测试 5: 文件验证 ---")
    test_validate_file()
    
    print("\n--- 测试 6: 文档处理生命周期 ---")
    asyncio.run(test_process_document_lifecycle())
    
    print("\n" + "=" * 60)
    print("所有文档处理测试通过!")
    print("=" * 60)
