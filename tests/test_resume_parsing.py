"""
简历解析功能测试脚本

测试项：
1. PDF 文本提取完整性
2. 姓名智能提取
3. 完整文本注入到 System Prompt
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.resume_parser import parse_pdf
from app.services.prompt_builder import get_system_prompt, build_welcome_message


async def test_resume_parsing():
    """测试简历解析功能"""
    print("=" * 60)
    print("测试 1: 简历解析完整性")
    print("=" * 60)
    
    test_resume_path = Path(__file__).parent.parent / "backend" / "uploads" / "resume" / "test.pdf"
    
    if not test_resume_path.exists():
        print(f"[FAIL] 测试简历不存在: {test_resume_path}")
        print("请上传一份 PDF 简历到 backend/uploads/resume/test.pdf")
        return
    
    print(f"[PASS] 找到测试简历: {test_resume_path}")
    
    with open(test_resume_path, "rb") as f:
        file_bytes = f.read()
    
    cleaned_text, keywords, frequencies, position, candidate_name = parse_pdf(file_bytes)
    
    print(f"\n解析结果:")
    print(f"  - 候选人姓名: {candidate_name or '未识别'}")
    print(f"  - 求职岗位: {position or '未识别'}")
    print(f"  - 关键词数量: {len(keywords)}")
    print(f"  - Top 10 关键词: {', '.join(keywords[:10])}")
    print(f"  - 完整文本长度: {len(cleaned_text)} 字符")
    print(f"\n完整文本前 500 字符:")
    print("-" * 60)
    print(cleaned_text[:500].encode('gbk', errors='replace').decode('gbk'))
    print("-" * 60)
    
    if len(cleaned_text) < 100:
        print("[FAIL] 警告: 提取的文本过短，可能未完整读取简历")
    else:
        print(f"[PASS] 文本提取完整 ({len(cleaned_text)} 字符)")
    
    if not candidate_name:
        print("[WARN] 警告: 未能提取候选人姓名")
    else:
        print(f"[PASS] 姓名提取成功: {candidate_name}")
    
    print("\n" + "=" * 60)
    print("测试 2: System Prompt 注入完整简历")
    print("=" * 60)
    
    system_prompt = get_system_prompt(
        keywords=keywords,
        interview_type="technical",
        turn=1,
        position_name=position,
        candidate_name=candidate_name,
        resume_full_text=cleaned_text,
    )
    
    print(f"\nSystem Prompt 统计:")
    print(f"  - 总长度: {len(system_prompt)} 字符")
    print(f"  - 包含完整简历: {'候选人完整简历' in system_prompt}")
    print(f"  - 包含候选人姓名: {candidate_name in system_prompt if candidate_name else 'N/A'}")
    print(f"  - 包含求职岗位: {position in system_prompt if position else 'N/A'}")
    
    if "候选人完整简历" in system_prompt:
        start_idx = system_prompt.find("## 候选人完整简历")
        end_idx = min(start_idx + 800, len(system_prompt))
        print(f"\nSystem Prompt 中的简历部分 (前 800 字符):")
        print("-" * 60)
        print(system_prompt[start_idx:end_idx].encode('gbk', errors='replace').decode('gbk'))
        print("-" * 60)
    
    print("\n" + "=" * 60)
    print("测试 3: 开场白生成（含完整简历）")
    print("=" * 60)
    
    try:
        welcome_text = await build_welcome_message(
            keywords=keywords,
            interview_type="technical",
            position_name=position,
            candidate_name=candidate_name,
            resume_full_text=cleaned_text,
        )
        print(f"\n[PASS] 开场白生成成功:")
        print("-" * 60)
        print(welcome_text.encode('gbk', errors='replace').decode('gbk'))
        print("-" * 60)
    except Exception as e:
        print(f"[FAIL] 开场白生成失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_resume_parsing())
