"""
测试面试阶段配置热更新

测试项：
1. 读取 interview_config.yaml 成功
2. 修改 YAML 后 force_reload 实时生效
3. 缺失/损坏时降级为默认配置
4. get_phase_for_turn 正确映射轮次到阶段
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.interview_config import (
    get_config,
    get_phase_for_turn,
    get_progress_hint,
    update_config_file,
)


def test_load_config():
    config = get_config(force_reload=True)
    assert "max_turns" in config, "应包含 max_turns"
    assert "phases" in config, "应包含 phases"
    assert len(config["phases"]) >= 5, "应至少有 5 个阶段"
    print(f"PASS: 配置加载成功 - max_turns={config['max_turns']}, phases={len(config['phases'])}")


def test_phase_mapping():
    config = get_config()
    
    phase1 = get_phase_for_turn(1, config)
    assert phase1 is not None, "第 1 轮应有对应阶段"
    assert phase1["rounds"][0] <= 1 <= phase1["rounds"][1]
    
    phase5 = get_phase_for_turn(5, config)
    assert phase5 is not None, "第 5 轮应有对应阶段"
    
    phase15 = get_phase_for_turn(15, config)
    assert phase15 is not None, "第 15 轮应有对应阶段"
    
    print("PASS: 轮次到阶段映射正确:")
    for turn in [1, 3, 5, 9, 12, 14]:
        phase = get_phase_for_turn(turn, config)
        phase_name = phase["name"] if phase else "超出范围"
        print(f"  Turn {turn} -> {phase_name}")


def test_progress_hint():
    hint = get_progress_hint(1, 15)
    assert "当前阶段" in hint or "处于" in hint, "应包含进度提示"
    
    hint_14 = get_progress_hint(14, 15)
    assert "倒数" in hint_14 or "总结" in hint_14 or "2 轮" in hint_14, "接近结束应有收尾提示"
    
    hint_15 = get_progress_hint(15, 15)
    assert "END" in hint_15 or "结束" in hint_15 or "总结" in hint_15, "最后一轮应强制结束"
    
    print("PASS: 进度提示正确:")
    print(f"  Turn 1/15: {hint[:60]}...")
    print(f"  Turn 14/15: {hint_14[:60]}...")
    print(f"  Turn 15/15: {hint_15[:60]}...")


def test_config_file_update():
    new_content = """
max_turns: 12
phases:
  - name: "自我介绍"
    rounds: [1, 2]
    description: "开场"
    instructions: "引导候选人自我介绍"
  - name: "技术考察"
    rounds: [3, 8]
    description: "技术考察"
    instructions: "深入技术提问"
  - name: "收尾"
    rounds: [9, 12]
    description: "总结"
    instructions: "总结面试表现"
global_instructions: "保持专业"
"""
    success, message = update_config_file(new_content)
    assert success, f"配置更新应成功，实际: {message}"
    
    config = get_config(force_reload=True)
    assert config["max_turns"] == 12, f"max_turns 应更新为 12，实际: {config['max_turns']}"
    assert len(config["phases"]) == 3, f"phases 应更新为 3 个，实际: {len(config['phases'])}"
    print(f"PASS: 配置文件热更新成功 - max_turns={config['max_turns']}, phases={len(config['phases'])}")
    
    get_config(force_reload=True)


def test_config_invalid_yaml_fallback():
    from app.services.interview_config import _load_raw_config
    
    with patch("app.services.interview_config._CONFIG_PATH") as mock_path:
        mock_path.exists.return_value = True
        with patch("builtins.open", side_effect=Exception("YAML parse error")):
            config = _load_raw_config()
            assert "max_turns" in config, "YAML 解析失败应使用默认配置"
            assert config["max_turns"] == 15, "默认 max_turns 应为 15"
    
    print("PASS: YAML 解析失败降级为默认配置")


if __name__ == "__main__":
    print("=" * 60)
    print("面试阶段配置热更新测试")
    print("=" * 60)
    
    print("\n--- 测试 1: 配置加载 ---")
    test_load_config()
    
    print("\n--- 测试 2: 轮次到阶段映射 ---")
    test_phase_mapping()
    
    print("\n--- 测试 3: 进度提示 ---")
    test_progress_hint()
    
    print("\n--- 测试 4: 配置文件热更新 ---")
    test_config_file_update()
    
    print("\n--- 测试 5: 无效 YAML 降级 ---")
    test_config_invalid_yaml_fallback()
    
    print("\n" + "=" * 60)
    print("所有配置热更新测试通过!")
    print("=" * 60)
