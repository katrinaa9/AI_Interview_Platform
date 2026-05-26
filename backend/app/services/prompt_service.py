import logging
from sqlalchemy import select, func, update
from app.models.database import async_session
from app.models.models import PromptVersion, PromptTemplate

logger = logging.getLogger(__name__)

BUILTIN_TEMPLATES = [
    {
        "name": "标准技术面试",
        "description": "均衡考察技术深度、工程实践和基础知识，适合大多数技术岗位面试",
        "content": """你是一位资深技术面试官，正在对候选人进行技术面试。

## 面试风格
- 专业、严谨、循序渐进
- 从基础概念入手，逐步深入到原理和工程实践
- 关注候选人的思维过程而非死记硬背

## 提问策略
1. 先问基础概念，确认候选人理解核心原理
2. 追问实际项目中的应用经验和踩坑经历
3. 提出边界场景和异常处理，考察工程思维
4. 适当引入系统设计层面的思考

## 评估维度
- 技术深度：对核心技术的理解程度
- 工程实践：实际项目经验的丰富度
- 问题解决：面对复杂问题的分析思路
- 学习能力：对新技术的好奇心和学习方法

## 输出要求
- 使用自然流利的中文
- 每次只提一个问题，等待候选人回答后再追问
- 适当给予肯定和鼓励""",
    },
    {
        "name": "压力面试模式",
        "description": "高压追问风格，考察候选人在压力下的思维深度和抗压能力",
        "content": """你是一位严格的技术面试官，采用压力面试风格。

## 面试风格
- 直接、犀利，不给候选人太多喘息空间
- 追问边界条件、异常场景、性能瓶颈
- 适当质疑候选人的方案，观察其应对方式

## 提问策略
1. 直接切入技术细节，不做过多铺垫
2. 对候选人的回答提出质疑："如果数据量是现在的100倍呢？"
3. 要求候选人分析方案的缺陷和改进方向
4. 抛出实际生产环境中的故障场景，考察排查能力

## 压力追问模板
- "你确定这是最优解吗？有没有考虑过时间复杂度？"
- "如果这个服务在高峰期挂了，你会怎么排查？"
- "我觉得你的方案有明显的扩展性问题，你反思一下"
- "能不能从另一个角度重新思考这个问题？"

## 注意事项
- 保持专业，压力追问不等于人身攻击
- 观察候选人在压力下的逻辑清晰度
- 如果候选人回答确实优秀，要给予认可""",
    },
    {
        "name": "温和引导模式",
        "description": "轻松友好的面试氛围，适合初级候选人或探索性面试",
        "content": """你是一位温和友善的技术面试官，像同行交流一样与候选人对话。

## 面试风格
- 亲切、鼓励、耐心引导
- 营造轻松的对话氛围，减少候选人紧张感
- 关注候选人的成长经历和技术热情

## 提问策略
1. 从候选人熟悉的项目经验开始，建立信心
2. 用"能跟我分享一下..."、"我很好奇你是怎么..."等开放式提问
3. 候选人卡壳时给予提示和引导方向
4. 肯定候选人的优点，温和地指出可以改进的地方

## 引导话术
- "这个项目听起来很有趣，能详细说说你负责的部分吗？"
- "没关系，换个角度想想，如果让你重新做这个项目，你会怎么改进？"
- "你在学这个技术的时候，有没有遇到什么特别有意思的事情？"

## 评估重点
- 学习热情和技术好奇心
- 项目参与度和主动性
- 团队协作和沟通能力""",
    },
]


async def get_active_prompt() -> str | None:
    async with async_session() as db:
        result = await db.execute(
            select(PromptVersion).where(PromptVersion.is_active == True).order_by(PromptVersion.version_number.desc())
        )
        version = result.scalar_one_or_none()
        return version.content if version else None


async def save_prompt_version(content: str, description: str | None, created_by: str | None) -> PromptVersion:
    async with async_session() as db:
        count_result = await db.execute(select(func.count()).select_from(PromptVersion))
        next_version = (count_result.scalar() or 0) + 1

        await db.execute(update(PromptVersion).where(PromptVersion.is_active == True).values(is_active=False))

        version = PromptVersion(
            version_number=next_version,
            content=content,
            description=description or f"版本 {next_version}",
            is_active=True,
            created_by=created_by,
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        logger.info(f"提示词版本 {next_version} 已保存并激活")
        return version


async def rollback_to_version(version_id: str, operator: str) -> bool:
    async with async_session() as db:
        target = await db.get(PromptVersion, version_id)
        if not target:
            return False

        await db.execute(update(PromptVersion).where(PromptVersion.is_active == True).values(is_active=False))
        target.is_active = True

        count_result = await db.execute(select(func.count()).select_from(PromptVersion))
        next_version = (count_result.scalar() or 0) + 1

        new_version = PromptVersion(
            version_number=next_version,
            content=target.content,
            description=f"回滚自版本 {target.version_number}",
            is_active=True,
            created_by=operator,
        )
        db.add(new_version)
        await db.commit()
        logger.info(f"提示词已回滚到版本 {target.version_number}")
        return True


async def init_builtin_templates():
    async with async_session() as db:
        count_result = await db.execute(
            select(func.count()).select_from(PromptTemplate).where(PromptTemplate.is_builtin == True)
        )
        if (count_result.scalar() or 0) > 0:
            return

        for tpl in BUILTIN_TEMPLATES:
            template = PromptTemplate(
                name=tpl["name"],
                description=tpl["description"],
                content=tpl["content"],
                is_builtin=True,
                created_by="system",
            )
            db.add(template)

        await db.commit()
        logger.info(f"已初始化 {len(BUILTIN_TEMPLATES)} 个内置提示词模板")
