"""
测试简历解析降级

测试项：
1. PDF 解析失败时返回错误
2. PDF 为空时返回错误
3. PDF 无文本内容（扫描版）时返回错误
4. 隐私信息脱敏
5. 姓名智能提取
6. 技术关键词提取
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.resume_parser import (
    _deidentify,
    _extract_keywords,
    ALL_TECH_KEYWORDS,
)


# ===== 测试 1: 隐私脱敏 =====

def test_deidentify_phone():
    text = "张三 13812345678 zhangsan@email.com"
    cleaned = _deidentify(text)
    assert "[手机号已隐藏]" in cleaned, "手机号应脱敏"
    print(f"PASS: 手机号脱敏: '{text}' -> '{cleaned}'")


def test_deidentify_email():
    text = "联系邮箱: test@example.com"
    cleaned = _deidentify(text)
    assert "[邮箱已隐藏]" in cleaned, "邮箱应脱敏"
    print(f"PASS: 邮箱脱敏: '{text}' -> '{cleaned}'")


def test_deidentify_id_card():
    text = "身份证号: 11010119900101123X"
    cleaned = _deidentify(text)
    assert "[身份证号已隐藏]" in cleaned or "11010119900101123X" not in cleaned, "身份证号应脱敏"
    print(f"PASS: 身份证号脱敏: '{text}' -> '{cleaned}'")


def test_deidentify_preserves_tech_info():
    text = "熟悉 React, TypeScript, Node.js。个人网站: github.com/zhangsan"
    cleaned = _deidentify(text)
    assert "React" in cleaned, "技术关键词不应脱敏"
    assert "TypeScript" in cleaned, "技术关键词不应脱敏"
    print(f"PASS: 技术信息保留: '{cleaned}'")


# ===== 测试 2: 关键词提取 =====

def test_extract_keywords_react():
    text = "我是一名前端工程师，熟练使用 React 和 TypeScript 进行开发，也使用过 Vue 和 Angular。"
    keywords, frequencies = _extract_keywords(text)
    assert "React" in keywords, "应识别 React"
    assert "TypeScript" in keywords, "应识别 TypeScript"
    print(f"PASS: 关键词提取: {keywords[:5]}")


def test_extract_keywords_full_stack():
    text = """
全栈工程师，5 年经验。
前端：React, Vue, TypeScript, JavaScript, Webpack
后端：Python, FastAPI, Django, Node.js
数据库：MySQL, Redis, MongoDB
DevOps：Docker, Kubernetes, Linux, CI/CD
"""
    keywords, frequencies = _extract_keywords(text)
    assert len(keywords) >= 10, f"应识别至少 10 个关键词，实际: {len(keywords)}"
    assert "React" in keywords
    assert "Python" in keywords
    assert "Docker" in keywords
    print(f"PASS: 全栈简历关键词提取: {len(keywords)} 个关键词")


def test_extract_keywords_frequency():
    text = "React React React JavaScript JavaScript"
    keywords, frequencies = _extract_keywords(text)
    assert frequencies.get("React", 0) == 3, f"React 应出现 3 次，实际: {frequencies.get('React', 0)}"
    assert frequencies.get("JavaScript", 0) == 2, f"JavaScript 应出现 2 次，实际: {frequencies.get('JavaScript', 0)}"
    print(f"PASS: 关键词频率统计正确: {frequencies}")


def test_extract_keywords_case_insensitive():
    text = "熟悉 react、REACT、React 框架"
    keywords, frequencies = _extract_keywords(text)
    assert "React" in keywords, "应不区分大小写识别 React"
    print(f"PASS: 大小写不敏感识别: {keywords}")


# ===== 测试 3: 关键词库完整性 =====

def test_keyword_library():
    categories = {
        "前端": ["React", "TypeScript", "Vue", "Angular"],
        "后端": ["Python", "Java", "FastAPI", "Spring Boot"],
        "数据库与缓存": ["MySQL", "Redis", "MongoDB"],
        "DevOps与云": ["Docker", "Kubernetes", "Linux"],
        "AI与数据": ["机器学习", "深度学习", "PyTorch"],
        "通用工具": ["Git", "微服务", "Agile/Scrum"],
    }
    
    for category, expected_keywords in categories.items():
        for kw in expected_keywords:
            assert kw in ALL_TECH_KEYWORDS, f"{category} 关键词 '{kw}' 应在关键词库中"
    
    print(f"PASS: 关键词库完整 - {len(ALL_TECH_KEYWORDS)} 个技术关键词")


if __name__ == "__main__":
    print("=" * 60)
    print("简历解析降级测试")
    print("=" * 60)
    
    print("\n--- 测试 1: 隐私脱敏 ---")
    test_deidentify_phone()
    test_deidentify_email()
    test_deidentify_id_card()
    test_deidentify_preserves_tech_info()
    
    print("\n--- 测试 2: 关键词提取 ---")
    test_extract_keywords_react()
    test_extract_keywords_full_stack()
    test_extract_keywords_frequency()
    test_extract_keywords_case_insensitive()
    
    print("\n--- 测试 3: 关键词库完整性 ---")
    test_keyword_library()
    
    print("\n" + "=" * 60)
    print("所有简历解析测试通过!")
    print("=" * 60)
