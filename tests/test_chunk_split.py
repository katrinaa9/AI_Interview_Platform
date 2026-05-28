#!/usr/bin/env python3
"""
测试文档切片功能
测试用例：15道题目的文档，验证是否能正确分割成15个chunks
"""

import sys
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.document_processor import split_chunks, _find_qa_boundaries

# 测试文档内容（15道题目）
TEST_DOCUMENT = """1. 什么是JavaScript的闭包？
闭包是指有权访问另一个函数作用域中的变量的函数。创建闭包的常见方式是在一个函数内创建另一个函数。

2. 解释React中的虚拟DOM
虚拟DOM是React使用的一种编程概念，它创建目标真实DOM的虚拟表示。React使用虚拟DOM来最小化实际DOM的更新次数，从而提高性能。

3. TypeScript中interface和type的区别是什么？
interface主要用于定义对象的结构，可以被扩展和实现；type可以定义任意类型，包括基本类型、联合类型和交叉类型。

4. 如何理解Python的装饰器？
装饰器是Python的一个高级特性，它允许在不修改原函数代码的情况下，动态地增加函数的功能。装饰器本质上是一个返回函数的函数。

5. 简述HTTP和HTTPS的区别
HTTP是明文传输协议，HTTPS是在HTTP基础上增加了SSL/TLS加密层。HTTPS更安全但性能开销更大，需要证书。

6. 什么是SQL注入？如何防范？
SQL注入是通过在Web表单中插入SQL代码片段来恶意操作数据库的攻击方式。防范措施包括使用参数化查询、输入验证和最小权限原则。

7. Redis的数据类型有哪些？
Redis支持5种基本数据类型：String（字符串）、Hash（哈希）、List（列表）、Set（集合）、ZSet（有序集合）。

8. Docker容器和虚拟机的区别
容器共享宿主机的操作系统内核，启动快、资源占用少；虚拟机有完整的操作系统，隔离性更强但资源消耗大。

9. Linux中如何查看进程状态？
使用ps命令可以查看进程状态，常用选项有ps aux、ps -ef。top命令可以实时显示进程状态。

10. TCP三次握手的过程是什么？
第一次握手：客户端发送SYN报文；第二次握手：服务器回复SYN+ACK；第三次握手：客户端回复ACK，连接建立。

11. 快速排序算法的时间复杂度
快速排序的平均时间复杂度为O(n log n)，最坏情况为O(n²)。它是一种分治算法，通过选择基准元素将数组分成两部分。

12. 单例设计模式的实现方式
单例模式确保一个类只有一个实例。常见实现方式包括：饿汉式、懒汉式、双重检查锁、静态内部类和枚举。

13. Git中rebase和merge的区别
merge会创建一个新的合并提交，保留完整的分支历史；rebase会将提交移到目标分支的顶端，创建线性历史。

14. CI/CD流程包括哪些环节？
CI/CD包括：代码提交、自动构建、自动测试、代码质量检查、自动部署到测试环境、集成测试、部署到生产环境。

15. 如何处理JavaScript中的异步操作？
JavaScript处理异步的方式有：回调函数、Promise、async/await。async/await是最现代的写法，让异步代码看起来像同步代码。
"""

def test_chunk_split():
    print("=" * 60)
    print("测试文档切片功能")
    print("=" * 60)
    print(f"\n原始文档长度: {len(TEST_DOCUMENT)} 字符")
    print(f"预期题目数量: 15")
    
    # 查找Q&A边界
    boundaries = _find_qa_boundaries(TEST_DOCUMENT)
    print(f"\n检测到的边界数量: {len(boundaries)}")
    print(f"边界位置: {boundaries}")
    
    # 执行切片
    chunks = split_chunks(TEST_DOCUMENT)
    print(f"\n生成的chunks数量: {len(chunks)}")
    
    # 验证每个chunk
    print("\n" + "=" * 60)
    print("Chunks详情:")
    print("=" * 60)
    
    for i, chunk in enumerate(chunks, 1):
        # 找到chunk中的题目编号
        import re
        match = re.search(r'(\d+)\.', chunk[:50])
        question_num = match.group(1) if match else "未知"
        
        print(f"\n【Chunk {i}】题目 {question_num}")
        print(f"  长度: {len(chunk)} 字符")
        # 使用 ascii-safe 编码避免 Windows GBK 编码问题
        preview = chunk[:100].replace('\n', ' ')
        print(f"  预览: {preview.encode('gbk', errors='replace').decode('gbk')[:90]}...")
        print("-" * 60)
    
    # 验证结果
    print("\n" + "=" * 60)
    print("验证结果:")
    print("=" * 60)
    
    if len(chunks) == 15:
        print("[PASS] 成功分割成15个chunks")
    else:
        print(f"[FAIL] 期望15个chunks，实际得到{len(chunks)}个")
        return False
    
    # 检查每个chunk是否包含完整的题目
    all_complete = True
    for i, chunk in enumerate(chunks, 1):
        if len(chunk) < 50:
            print(f"[FAIL] Chunk {i} 过短，可能内容不完整")
            all_complete = False
        if "答案" not in chunk and "答" not in chunk:
            # 检查是否包含答案内容
            has_answer = any(keyword in chunk for keyword in ["是指", "包括", "支持", "使用", "可以"])
            if not has_answer:
                print(f"[WARN] Chunk {i} 可能缺少答案内容")
    
    if all_complete:
        print("[PASS] 所有chunks内容完整")
    
    return len(chunks) == 15 and all_complete

if __name__ == "__main__":
    success = test_chunk_split()
    sys.exit(0 if success else 1)
