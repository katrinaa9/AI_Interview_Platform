"""
测试套件统一运行脚本

运行方式:
    python tests/run_all_tests.py

或直接运行单个测试:
    python tests/test_llm_failover.py
"""

import sys
import os
import importlib
from pathlib import Path

# 添加项目路径
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

TEST_FILES = [
    "test_llm_failover",
    "test_evaluator_fallback",
    "test_jwt_auth_rbac",
    "test_sse_streaming",
    "test_rag_engine",
    "test_rate_limit",
    "test_concurrency_slots",
    "test_mock_degradation",
    "test_welcome_fallback",
    "test_config_hot_reload",
    "test_document_processing",
    "test_prompt_preview",
    "test_audit_logging",
    "test_resume_parser_fallback",
    "test_sse_reconnect",
]


def main():
    print("=" * 70)
    print(" " * 15 + "AceInterviewer 测试套件")
    print("=" * 70)
    
    passed = 0
    failed = 0
    errors = []
    
    for test_name in TEST_FILES:
        print(f"\n{'=' * 70}")
        print(f"运行: {test_name}")
        print(f"{'=' * 70}")
        try:
            mod = importlib.import_module(f"tests.{test_name}")
            if hasattr(mod, "main") and callable(mod.main):
                mod.main()
            else:
                print(f"  ⚠️  测试文件 {test_name} 没有 main() 函数，跳过")
            passed += 1
        except Exception as e:
            failed += 1
            error_msg = f"❌ {test_name}: {e}"
            errors.append(error_msg)
            print(f"\n  {error_msg}")
    
    print(f"\n{'=' * 70}")
    print(f"测试汇总: {passed} 通过, {failed} 失败, 共 {len(TEST_FILES)} 个测试脚本")
    if errors:
        print(f"\n失败详情:")
        for e in errors:
            print(f"  {e}")
    print(f"{'=' * 70}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
