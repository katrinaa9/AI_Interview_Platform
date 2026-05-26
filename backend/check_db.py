"""
数据库初始化与检查脚本
用法：python check_db.py
"""
import asyncio
import sys
from app.models.database import engine, Base
from app.models.models import User, Resume, QuestionBank, InterviewSession, EvaluationReport


async def check_and_init():
    print("=" * 50)
    print("AceInterviewer 数据库检查与初始化")
    print("=" * 50)

    # 1. 测试 MySQL 连接
    db_url = str(engine.url).replace(
        engine.url.password, "***" if engine.url.password else ""
    )
    print(f"\n[1/3] 测试数据库连接: {db_url}")

    try:
        async with engine.begin() as conn:
            result = await conn.exec_driver_sql("SELECT 1")
            row = result.fetchone()
            print(f"  连接成功! MySQL 版本信息: {row}")
    except Exception as e:
        print(f"\n  *** 连接失败！请检查 MySQL 是否已启动且 .env 配置正确 ***")
        print(f"  错误详情: {e}")
        print("\n  请确认：")
        print("  1. MySQL 服务已启动（services.msc 检查 MySQL80 状态）")
        print("  2. .env 文件中的 MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD 正确")
        print("  3. 已执行建库 SQL")
        sys.exit(1)

    # 2. 检查/创建表
    print("\n[2/3] 检查数据库表...")
    try:
        # 收集所有模型对应的表
        all_tables = {cls.__tablename__ for cls in Base.__subclasses__()}
        print(f"  预期表: {', '.join(sorted(all_tables))}")

        async with engine.connect() as conn:
            # 检查已有表
            from sqlalchemy import inspect
            def get_tables(connection):
                inspector = inspect(connection)
                return set(inspector.get_table_names())

            existing = await conn.run_sync(get_tables)
            missing = all_tables - existing

            if missing:
                print(f"  缺少表: {', '.join(sorted(missing))}")
                print("  正在创建...")
                await conn.run_sync(Base.metadata.create_all)
                await conn.commit()
                print("  创建完成!")
            else:
                print("  所有表已存在，无需创建")
    except Exception as e:
        print(f"\n  *** 表检查/创建失败 ***")
        print(f"  错误详情: {e}")
        sys.exit(1)

    # 3. 验证表结构
    print("\n[3/3] 验证表结构...")
    try:
        async with engine.connect() as conn:
            from sqlalchemy import inspect
            def verify(connection):
                inspector = inspect(connection)
                result = {}
                for table_name in ["users", "resumes", "question_bank", "interview_sessions", "evaluation_reports"]:
                    cols = inspector.get_columns(table_name)
                    result[table_name] = len(cols)
                return result

            counts = await conn.run_sync(verify)
            for name, count in counts.items():
                print(f"  {name}: {count} 个字段 — OK")
    except Exception as e:
        print(f"  验证警告: {e}")

    print("\n" + "=" * 50)
    print("数据库初始化完成，可以启动后端了")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(check_and_init())