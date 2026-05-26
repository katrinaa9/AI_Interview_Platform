"""
题库种子数据脚本

用法:
    python seed_data.py          # 插入种子数据（跳过已存在的题目）
    python seed_data.py --reset  # 清空题库后重新插入

该脚本会检查题库中是否已有数据，避免重复插入。
"""

import asyncio
import sys
import uuid
from sqlalchemy import select, delete
from app.models.database import async_session
from app.models.models import QuestionBank

# ===== 种子题目（按技术栈分类） =====
SEED_QUESTIONS = [
    # ---------- React ----------
    {
        "category": "React",
        "question_text": "请解释 React 中的虚拟 DOM（Virtual DOM）工作原理，以及它如何提升渲染性能？",
        "reference_answer": "虚拟 DOM 是真实 DOM 的轻量级 JS 对象表示。React 在内存中维护两颗虚拟 DOM 树（当前和更新后），通过 Diff 算法（Reconciliation）找出最小差异集合，最后批量更新真实 DOM。这避免了频繁的直接 DOM 操作，提升了渲染性能。",
        "difficulty": "medium",
    },
    {
        "category": "React",
        "question_text": "React Hooks 中 useEffect 和 useLayoutEffect 的区别是什么？分别在什么场景下使用？",
        "reference_answer": "useEffect 在浏览器完成布局和绘制之后异步执行，不会阻塞屏幕更新，适用于数据获取、订阅等场景。useLayoutEffect 在 DOM 变更后、浏览器绘制前同步执行，会阻塞渲染，适用于需要读取 DOM 布局信息并同步修改的场景（如测量元素尺寸后立即更新样式），避免页面闪烁。",
        "difficulty": "medium",
    },
    {
        "category": "React",
        "question_text": "什么是 React Fiber 架构？它解决了什么问题？",
        "reference_answer": "Fiber 是 React 16 引入的新的调和引擎（Reconciler）。它解决了旧 Stack Reconciler 的同步递归不可中断问题。Fiber 将渲染工作拆分为可中断的小单元（Fiber Node），通过优先级调度（RequestIdleCallback），高优先级任务可以打断低优先级渲染，使 React 能保持 60fps 的流畅交互体验。",
        "difficulty": "hard",
    },
    {
        "category": "React",
        "question_text": "请简述 React 中的状态提升（Lifting State Up）和 Context API 的使用场景。",
        "reference_answer": "状态提升是指将多个子组件需要共享的状态提升到它们最近的公共父组件中管理，通过 props 向下传递。适用场景：少数 2-3 层组件间共享状态。Context API 允许跨层级传递数据而无需手动逐层传递 props，适用于全局主题、用户认证信息、语言偏好等需要被多层级组件访问的数据。二者选择原则：简单场景用状态提升，深层嵌套或全局场景用 Context。",
        "difficulty": "easy",
    },

    # ---------- TypeScript ----------
    {
        "category": "TypeScript",
        "question_text": "TypeScript 中 interface 和 type 有什么区别？分别在什么时候使用？",
        "reference_answer": "interface 支持声明合并（同名 interface 自动合并），可被类实现（implements）和扩展（extends），更适合定义对象形状和公共 API。type 支持联合类型（|）、交叉类型（&）、元组、映射类型等，表达能力更强。推荐优先使用 interface 定义对象结构，需联合类型或复杂类型计算时用 type。",
        "difficulty": "medium",
    },
    {
        "category": "TypeScript",
        "question_text": "请解释 TypeScript 中的泛型（Generics）以及它的典型使用场景。",
        "reference_answer": "泛型允许在定义函数、接口或类时不预先指定具体类型，而在使用时再确定，从而在保持类型安全的同时实现代码复用。典型场景：通用工具函数（如泛型版本的 useState）、泛型接口（如 API 响应包装类型 `Response<T>`）、泛型约束（extends 关键字限制传入类型必须具备某些属性）。",
        "difficulty": "medium",
    },

    # ---------- Python ----------
    {
        "category": "Python",
        "question_text": "Python 中的 GIL（全局解释器锁）是什么？它如何影响多线程编程？",
        "reference_answer": "GIL（Global Interpreter Lock）是 CPython 解释器中的互斥锁，保证同一时刻只有一个线程执行 Python 字节码。这导致 CPU 密集型任务的 Python 多线程无法利用多核优势。对于 I/O 密集型任务（网络请求、文件读写），多线程仍有效（I/O 时会释放 GIL）。绕过方案：使用多进程（multiprocessing）、异步编程（asyncio）、或使用 C 扩展释放 GIL。",
        "difficulty": "hard",
    },
    {
        "category": "Python",
        "question_text": "Python 中 `__init__` 和 `__new__` 的区别是什么？",
        "reference_answer": "__new__ 是类方法，在实例创建前被调用，负责创建并返回实例对象（通常调用 super().__new__），常用于单例模式或继承不可变类型（如 str、int）。__init__ 是实例方法，在实例创建后被调用，负责初始化实例属性。__new__ 先于 __init__ 执行，且只有当 __new__ 返回当前类的实例时 __init__ 才会被调用。",
        "difficulty": "medium",
    },

    # ---------- FastAPI ----------
    {
        "category": "FastAPI",
        "question_text": "FastAPI 中的依赖注入（Depends）是如何工作的？它解决了什么问题？",
        "reference_answer": "FastAPI 的 Depends 是基于 Python 类型注解和可调用对象的依赖注入系统。它将公共逻辑（如数据库连接、认证校验、权限验证）抽取为独立函数，通过 Depends() 声明依赖关系。FastAPI 自动解析调用链、缓存可复用依赖（scope 内）、支持嵌套依赖。优点：代码复用、关注点分离、自动 OpenAPI 文档生成、方便测试 mock。",
        "difficulty": "medium",
    },
    {
        "category": "FastAPI",
        "question_text": "请解释 FastAPI 中的异步（async/await）和非异步路由的区别，以及如何在 async 路由中执行 CPU 密集型任务？",
        "reference_answer": "async def 路由在 asyncio 事件循环中运行，适合 I/O 密集型操作（数据库查询、网络请求），不会阻塞其他请求。def 路由会被在线程池中执行。在 async 路由中执行 CPU 密集型任务（如 PDF 解析、图像处理），应使用 `await asyncio.to_thread(func, args)` 或 `run_in_executor` 将任务放到线程池，避免阻塞事件循环。",
        "difficulty": "hard",
    },

    # ---------- MySQL ----------
    {
        "category": "MySQL",
        "question_text": "MySQL 中 InnoDB 存储引擎的索引底层数据结构是什么？为什么使用 B+ 树而不是红黑树或 Hash？",
        "reference_answer": "InnoDB 使用 B+ 树作为索引结构。原因：(1) B+ 树是多路搜索树，每个节点存储多个 key，极大降低了树的高度（磁盘 I/O 次数少）；(2) 所有数据存储在叶子节点且叶子节点之间用双向链表连接，范围查询只需遍历叶子链表，非常高效；(3) 相比红黑树（二叉树，高度大），相比 Hash（不支持范围查询、排序），B+ 树更适合磁盘 I/O 场景和数据库需求。",
        "difficulty": "hard",
    },
    {
        "category": "MySQL",
        "question_text": "请解释 SQL 中的 JOIN 类型及其区别：INNER JOIN、LEFT JOIN、RIGHT JOIN、FULL JOIN。",
        "reference_answer": "INNER JOIN 返回两表中匹配的行（交集）；LEFT JOIN 返回左表所有行 + 右表匹配行（右表无匹配则 NULL）；RIGHT JOIN 返回右表所有行 + 左表匹配行（左表无匹配则 NULL）；FULL JOIN 返回两表所有行（无论是否匹配，无匹配则 NULL，MySQL 不直接支持，用 LEFT JOIN UNION RIGHT JOIN 实现）。",
        "difficulty": "easy",
    },

    # ---------- Redis ----------
    {
        "category": "Redis",
        "question_text": "Redis 有哪些常见的数据类型？各自适合什么场景？",
        "reference_answer": "String：缓存、计数器、分布式锁（SETNX）；Hash：存储对象（如用户信息）；List：消息队列（LPUSH/RPOP）、最新消息列表；Set：去重、共同好友、标签；Sorted Set：排行榜、延迟队列（按分数排序）；Bitmap：签到统计、用户在线状态；HyperLogLog：UV 统计；Stream：可靠的消息队列。",
        "difficulty": "medium",
    },
    {
        "category": "Redis",
        "question_text": "请解释 Redis 的缓存雪崩、缓存穿透和缓存击穿，以及各自的解决方案。",
        "reference_answer": "缓存雪崩：大量 key 同时过期，请求直接打穿到 DB。方案：key 过期时间加随机值、多级缓存、限流降级。缓存穿透：查询不存在的数据（缓存和 DB 都没有），恶意攻击。方案：布隆过滤器预处理、空值缓存（短 TTL）。缓存击穿：热点 key 过期瞬间大量并发请求。方案：互斥锁（只有一个线程回源查 DB 并更新缓存）、永不过期（逻辑过期，异步刷新）。",
        "difficulty": "hard",
    },

    # ---------- Docker ----------
    {
        "category": "Docker",
        "question_text": "Docker 镜像（Image）和容器（Container）的区别是什么？Dockerfile 中的 CMD 和 ENTRYPOINT 有什么区别？",
        "reference_answer": "镜像：只读模板，包含运行应用所需的代码、运行时、库、环境变量等，是静态的。容器：镜像的运行实例，拥有可写层，是动态的。CMD 为容器提供默认命令和参数，可在 docker run 时被覆盖。ENTRYPOINT 定义容器的主命令，docker run 后的参数作为 ENTRYPOINT 的附加参数。二者常组合使用：ENTRYPOINT 定义可执行文件，CMD 定义默认参数。",
        "difficulty": "medium",
    },
    {
        "category": "Docker",
        "question_text": "Docker 的网络模式有哪些？默认的 bridge 模式是如何工作的？",
        "reference_answer": "网络模式：bridge（默认，容器间通过 docker0 虚拟网桥通信，容器与宿主机端口映射）、host（容器直接使用宿主机网络栈，性能最高但端口冲突）、none（无网络，完全隔离）、container（共享另一个容器的网络命名空间）、overlay（跨宿主机的 Swarm 模式网络）。bridge 模式下，每个容器分配虚拟网卡和内部 IP，通过 NAT 与外部通信。",
        "difficulty": "medium",
    },

    # ---------- 通用 ----------
    {
        "category": "Git",
        "question_text": "Git 中 merge 和 rebase 的区别是什么？分别在什么场景下使用？",
        "reference_answer": "merge 会创建一个新的合并提交，完整保留分支历史和分叉拓扑，适合公共分支（如 main 合并 feature 分支）或需要保留完整历史记录的场景。rebase 将当前分支的提交追加到目标分支最新提交之后，形成线性历史，提交历史更清晰，但会改写提交 SHA。rebase 适合在本地整理提交、同步上游变更（git pull --rebase）；切忌对已推送的公共提交做 rebase。",
        "difficulty": "medium",
    },
    {
        "category": "Linux",
        "question_text": "请解释 Linux 中的硬链接（Hard Link）和软链接/符号链接（Symbolic Link）的区别。",
        "reference_answer": "硬链接：指向同一 inode，与原文件完全平等，删除原文件不影响硬链接。不能跨文件系统、不能链接目录。软链接：存储目标路径的文本字符串，类似于 Windows 快捷方式，可跨文件系统、可链接目录。删除原文件后软链接失效（断链）。",
        "difficulty": "easy",
    },
    {
        "category": "计算机网络",
        "question_text": "请解释 HTTP 协议中 GET 和 POST 的区别，以及 HTTP/1.1 和 HTTP/2 的主要改进。",
        "reference_answer": "GET 用于获取资源，参数在 URL 中，可缓存、可收藏、幂等。POST 用于提交数据，参数在请求体中，不可缓存、非幂等。HTTP/2 主要改进：(1) 二进制分帧而非文本协议；(2) 多路复用（一个 TCP 连接并发多个请求/响应，解决队头阻塞）；(3) 头部压缩（HPACK 算法）；(4) 服务器推送（Server Push）。",
        "difficulty": "medium",
    },
    {
        "category": "算法与数据结构",
        "question_text": "请解释哈希表（Hash Table）的工作原理，以及如何处理哈希冲突？",
        "reference_answer": "哈希表通过哈希函数将 key 映射到数组索引（bucket），实现 O(1) 平均时间复杂度的查找。冲突处理：(1) 链地址法（Separate Chaining）：每个 bucket 维护链表/红黑树，冲突 key 追加到链表（Java HashMap 在链表长度 ≥8 时转为红黑树）；(2) 开放地址法（Open Addressing）：发生冲突时按某种探测序列（线性探测、二次探测、双重哈希）寻找下一个空槽。负载因子过高时触发扩容（rehash），重新分配所有 key。",
        "difficulty": "medium",
    },
]


async def seed_database(reset: bool = False):
    """向 question_bank 表插入种子数据"""
    async with async_session() as db:
        # 可选：清空已有数据
        if reset:
            await db.execute(delete(QuestionBank))
            await db.commit()
            print("[seed] 已清空题库")

        # 检查是否已有数据
        result = await db.execute(select(QuestionBank).limit(1))
        if result.scalar_one_or_none() and not reset:
            print("[seed] 题库已包含数据，跳过种子插入（使用 --reset 强制重置）")
            return

        count = 0
        for q in SEED_QUESTIONS:
            question = QuestionBank(
                id=str(uuid.uuid4()),
                category=q["category"],
                question_text=q["question_text"],
                reference_answer=q["reference_answer"],
                difficulty=q["difficulty"],
            )
            db.add(question)
            count += 1

        await db.commit()
        print(f"[seed] 成功插入 {count} 条种子题目")

    # 关闭连接池
    await async_session().bind.dispose()


if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    asyncio.run(seed_database(reset=reset_flag))