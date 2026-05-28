# AceInterviewer - AI 模拟面试平台

> 沉浸式 AI 模拟面试平台，基于大语言模型驱动的智能面试官，为求职者提供真实、专业、可评估的模拟面试体验。

![Tech Stack](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React_18-61DAFB?style=flat&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.11+-3776AB?style=flat&logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=flat&logo=mysql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)

---

## 目录

- [项目概述](#项目概述)
- [核心功能](#核心功能)
- [技术栈与架构](#技术栈与架构)
- [环境要求](#环境要求)
- [安装部署](#安装部署)
  - [开发环境配置](#开发环境配置)
  - [生产环境部署](#生产环境部署)
  - [常见问题解决](#常见问题解决)
- [使用指南](#使用指南)
  - [基本操作流程](#基本操作流程)
  - [核心功能演示](#核心功能演示)
  - [管理员后台](#管理员后台)
- [API 接口文档](#api-接口文档)
- [项目目录结构](#项目目录结构)
- [配置说明](#配置说明)
- [贡献指南](#贡献指南)
- [许可证](#许可证)
- [联系方式与鸣谢](#联系方式与鸣谢)

---

## 项目概述

**AceInterviewer** 是一款面向求职者的 AI 模拟面试平台，通过大语言模型（DeepSeek / 通义千问）扮演资深技术面试官，基于候选人上传的 PDF 简历进行个性化的技术面试。平台支持三种面试风格（技术面、压力面、轻松聊天），面试全程采用 SSE 流式输出，模拟真实面试对话体验。面试结束后，AI 自动生成六维雷达评分和详细评估报告。

平台同时提供完整的管理员后台，支持 RAG 知识库文档管理、题库维护、System Prompt 版本配置和操作日志审计。

### 核心价值

- **个性化面试**：基于简历关键词和完整简历内容，AI 面试官进行针对性提问
- **真实面试体验**：SSE 流式对话 + 分阶段面试流程（自我介绍 -> 技术考察 -> 压力追问 -> 职业素养 -> 收尾）
- **专业评估报告**：六维雷达评分（技术深度、逻辑表达、专业知识、应变能力、沟通协作、项目实践）+ 五点文本反馈
- **RAG 知识增强**：管理员上传文档自动切片入库，面试时基于知识库进行检索增强提问
- **双模型高可用**：DeepSeek + 通义千问主备切换，确保面试服务稳定可用

---

## 核心功能

### 用户端

| 功能 | 说明 |
|------|------|
| **用户注册/登录** | JWT 认证，支持 student/admin 两种角色 |
| **简历上传与解析** | PDF 简历上传，PyMuPDF 智能解析提取技术栈关键词和姓名 |
| **AI 模拟面试** | 三种面试类型（技术面/压力面/轻松聊天），SSE 流式对话，最多 15 轮 |
| **面试评估报告** | 六维雷达图评分 + AI 详细反馈（总体评价、核心优势、薄弱环节、改进建议） |
| **历史面试记录** | 查看过往面试记录和评估报告，支持多次面试对比 |
| **暗色/亮色主题** | 一键切换，全局生效 |

### 管理员端

| 功能 | 说明 |
|------|------|
| **数据仪表盘** | 题库总量、文档数、用户数、面试场次统计、近期操作日志 |
| **题库管理** | 题目的增删改查，按分类/难度筛选，高频错题统计 |
| **知识库文档管理** | PDF/TXT 文档上传、自动切片入库、知识片段查看/编辑/删除 |
| **System Prompt 配置** | 提示词版本管理、模板管理、在线编辑与实时生效 |
| **操作日志** | 全局操作审计日志，支持按操作人/类型/状态筛选 |

---

## 技术栈与架构

### 系统架构

```
+------------------+       +-------------------+       +------------------+
|   React SPA      |       |   FastAPI Server  |       |   DeepSeek API   |
|   (Vite + TS)    | <---> |   (async/await)   | <---> |   通义千问 API    |
+------------------+       +-------------------+       +------------------+
                                  |        |
                           +------+        +------+
                           |                     |
                    +------+------+      +------+------+
                    |   MySQL     |      |    Redis    |
                    |  (asyncmy)  |      | (滑动窗口)  |
                    +-------------+      +-------------+
```

### 前端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.3 | UI 框架 |
| TypeScript | 5.6 | 类型安全 |
| Vite | 5.4 | 构建工具与开发服务器 |
| Zustand | 4.5 | 全局状态管理（轻量级） |
| React Router | 6.26 | 客户端路由 |
| TailwindCSS | 3.4 | 原子化 CSS 样式框架 |
| ECharts | 5.5 | 雷达图等数据可视化 |
| React Markdown | 9.0 | Markdown 内容渲染 |
| Lucide React | 0.441 | 图标库 |
| class-variance-authority | 0.7 | 组件变体管理 |

### 后端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.115 | 异步 Web 框架 |
| SQLAlchemy | 2.0 | ORM（异步模式 + asyncmy） |
| asyncmy | 0.2.9 | MySQL 异步驱动 |
| Redis | 5.0 | 缓存 + 滑动窗口限流 |
| PyMuPDF | 1.24 | PDF 简历解析 |
| OpenAI SDK | >=1.50 | LLM API 调用（DeepSeek + 通义千问均兼容） |
| sse-starlette | 2.1 | Server-Sent Events 流式响应 |
| Pydantic | 2.9 | 数据校验与序列化 |
| python-jose | 3.3 | JWT Token 签发与验证 |
| passlib + bcrypt | 1.7/4.0 | 密码哈希（SHA-256 预哈希 + bcrypt） |

### 核心架构设计

- **双模型 Failover**：DeepSeek 为主模型，通义千问为备用模型。超时、5xx 错误、限流时自动切换，认证错误不切换
- **RAG 检索增强**：简历关键词 -> Redis 缓存 -> MySQL 题库检索 -> 回写缓存，作为 LLM 参考上下文
- **Redis 滑动窗口限流**：基于 Sorted Set 实现，分层策略（面试 15 次/分钟、管理 200 次/分钟），Redis 不可用时自动降级放行
- **SSE 流式输出**：面试对话通过 Server-Sent Events 实时推送，前端逐字显示
- **Q&A 智能切片**：上传的知识库文档按 Q&A 边界自动分割，支持数字编号识别和段落合并

---

## 环境要求

| 依赖 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Python | 3.11 | 3.12 | 后端运行时 |
| Node.js | 18 | 20 LTS | 前端构建 |
| MySQL | 8.0 | 8.0+ | 主数据库 |
| Redis | 6.0 | 7.0+ | 缓存与限流（可选，不可用时自动降级） |

---

## 安装部署

### 开发环境配置

#### 1. 克隆项目

```bash
git clone <repository-url>
cd AI_Interview_Platform
```

#### 2. 数据库初始化

确保 MySQL 服务已启动，执行初始化脚本：

```bash
mysql -u root -p < backend/init.sql
```

或手动创建数据库：

```sql
CREATE DATABASE IF NOT EXISTS aceinterviewer
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

> 应用首次启动时会自动创建所有数据表（通过 SQLAlchemy `create_all`）。

#### 3. 后端配置

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 安装依赖
pip install -r requirements.txt

# 创建环境变量文件（在 backend/ 目录或项目根目录创建 .env）
```

在 `.env` 文件中配置以下环境变量：

```env
# 数据库连接
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=aceinterviewer
MYSQL_PASSWORD=aceinterviewer123
MYSQL_DATABASE=aceinterviewer

# Redis（可选）
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT 密钥（生产环境必须修改！）
JWT_SECRET=your-secret-key-change-in-production

# DeepSeek API Key（至少配置一个 LLM）
DEEPSEEK_API_KEY=sk-your-deepseek-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 通义千问 API Key（备用模型，推荐配置）
QWEN_API_KEY=sk-your-qwen-key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL_NAME=qwen-plus
```

```bash
# 插入种子题库数据（可选）
python seed_data.py

# 启动后端服务（默认端口 8000）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 4. 前端配置

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器（默认端口 3000）
npm run dev
```

#### 5. 验证启动

- 前端访问：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 生产环境部署

#### 后端部署

```bash
# 使用 Gunicorn + Uvicorn worker 启动
pip install gunicorn
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile -

# 确保生产环境的 .env 中：
# - JWT_SECRET 设置为强随机字符串
# - DEBUG=false
# - APP_ENV=production
```

#### 前端构建

```bash
cd frontend

# TypeScript 类型检查 + 构建
npm run build

# 构建产物在 dist/ 目录，使用 Nginx 等 Web 服务器托管
```

#### Nginx 反向代理配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态资源
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE 流式响应支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

### 常见问题解决

#### bcrypt 版本不兼容

```
问题：passlib 1.7.4 与 bcrypt >= 4.1 不兼容
解决：pip install bcrypt==4.0.1
```

#### MySQL 连接被拒绝

```
问题：asyncmy 连接报错 "Access denied"
解决：确认 MySQL 用户已授权，且 init.sql 已正确执行
      mysql -u root -p -e "GRANT ALL ON aceinterviewer.* TO 'aceinterviewer'@'localhost';"
```

#### Redis 连接失败

```
问题：Redis 不可用
解决：Redis 为可选依赖，不可用时系统自动降级（限流放行、缓存跳过）。
      如需启用，确保 Redis 服务已启动：redis-server
```

#### 前端开发代理 404

```
问题：前端 /api/* 请求返回 404
解决：确保后端服务在 localhost:8000 运行，vite.config.ts 已配置 proxy
```

#### LLM API Key 未配置

```
问题：启动日志显示 "未配置任何 LLM API Key，AI 功能将降级为 Mock 模式"
解决：在 .env 中至少配置 DEEPSEEK_API_KEY 或 QWEN_API_KEY 中的一个
```

---

## 使用指南

### 基本操作流程

```
用户注册 → 登录系统 → 上传 PDF 简历 → 选择面试类型 → AI 面试（SSE 流式对话）→ 结束面试 → 查看评估报告
```

#### 1. 注册与登录

- 访问 http://localhost:3000/login
- 新用户点击「注册」，输入用户名（2-50 字符）和密码（6-128 字符）
- 注册成功后自动登录并跳转到首页

#### 2. 上传简历

- 点击导航栏「上传简历」进入简历上传页面
- 上传 PDF 格式简历文件
- 系统自动解析简历，提取技术栈关键词和候选人姓名
- 确认关键词后可手动调整

#### 3. 开始面试

- 点击「开始面试」进入面试配置页面
- 选择面试类型：
  - **基础技术面**：编程语言、数据结构、计算机网络等核心知识
  - **压力面试**：高压追问、边界条件分析、抗压能力考察
  - **轻松聊天**：职业发展、项目经验交流
- AI 面试官自动生成个性化开场白
- 通过 SSE 流式输出，逐字显示面试官提问

#### 4. 面试对话

- 面试最多进行 **15 轮**对话
- 面试分为 5 个阶段：自我介绍 → 技术考察 → 压力追问 → 职业素养 → 收尾
- 输入回答后点击发送，AI 面试官会基于你的回答进行追问

#### 5. 查看评估报告

- 面试结束后自动生成评估报告
- 六维雷达图：技术深度、逻辑表达、专业知识、应变能力、沟通协作、项目实践
- 五点文本反馈：总体评价、核心优势、薄弱环节、详细分析、改进建议
- 支持查看历史面试记录和报告对比

### 管理员后台

- 管理员登录后，导航栏出现「管理后台」入口
- **仪表盘**：题库总量、文档数、知识片段数、今日/本周/本月面试场次
- **题库管理**：增删改查面试题目，按分类（React/Python/MySQL 等）和难度筛选
- **文档管理**：上传 PDF/TXT 文档，系统自动切片入库为知识片段，支持查看和编辑
- **Prompt 配置**：管理系统提示词版本，支持在线编辑和实时切换
- **操作日志**：审计所有管理员操作记录

### 创建管理员账户

默认注册用户为 `student` 角色。通过数据库直接提升为管理员：

```sql
UPDATE users SET role = 'admin' WHERE username = 'your-username';
```

---

## API 接口文档

后端内置 Swagger UI 交互式文档，启动后端后访问：

- **Swagger UI**：http://localhost:8000/docs
- **ReDoc**：http://localhost:8000/redoc

### 主要接口概览

#### 认证模块 (`/api/auth`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |

#### 简历模块 (`/api/resume`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/resume/upload` | 上传 PDF 简历 |
| GET | `/api/resume/keywords` | 获取简历关键词 |
| PUT | `/api/resume/keywords` | 更新简历关键词 |

#### 面试模块 (`/api/interview`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/interview/start` | 开始面试（返回会话 ID + 开场白） |
| POST | `/api/interview/chat` | 发送消息（SSE 流式响应） |
| POST | `/api/interview/end` | 结束面试（触发评估） |

#### 报告模块 (`/api/report`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/report/{session_id}` | 获取指定面试的评估报告 |
| GET | `/api/report/history/list` | 获取历史面试列表 |

#### 管理员模块 (`/api/admin`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/dashboard/stats` | 仪表盘统计数据 |
| GET/POST/PUT/DELETE | `/api/admin/questions/*` | 题库 CRUD |
| GET/POST/DELETE | `/api/admin/documents/*` | 文档管理 |
| GET | `/api/admin/documents/{id}/chunks` | 查看文档知识片段 |
| POST/PUT/DELETE | `/api/admin/documents/chunks/*` | 知识片段管理 |
| GET/POST | `/api/admin/prompt/*` | System Prompt 版本管理 |
| GET/POST/PUT/DELETE | `/api/admin/prompt/templates/*` | Prompt 模板管理 |
| GET | `/api/admin/audit/logs` | 操作日志查询 |

#### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 服务健康检查 |
| GET | `/health/db` | 数据库连通性检查 |

---

## 项目目录结构

```
AI_Interview_Platform/
├── backend/                         # 后端（FastAPI）
│   ├── app/
│   │   ├── api/                     # API 路由层
│   │   │   ├── auth.py              # 认证（注册/登录/JWT）
│   │   │   ├── resume.py            # 简历上传与解析
│   │   │   ├── interview.py         # 面试流程（开始/对话/结束）
│   │   │   ├── report.py            # 评估报告（查看/历史）
│   │   │   ├── admin.py             # 管理员路由注册
│   │   │   ├── admin_dashboard.py   # 仪表盘统计
│   │   │   ├── admin_documents.py   # 文档与知识片段管理
│   │   │   ├── admin_prompt.py      # Prompt 版本与模板管理
│   │   │   ├── admin_config.py      # 系统配置
│   │   │   └── admin_audit.py       # 操作日志
│   │   ├── core/                    # 核心基础设施
│   │   │   ├── redis.py             # Redis 连接池管理
│   │   │   ├── rate_limit.py        # 滑动窗口限流中间件
│   │   │   └── concurrency.py       # 并发槽位管理
│   │   ├── models/                  # 数据模型
│   │   │   ├── database.py          # SQLAlchemy 引擎与会话
│   │   │   └── models.py            # ORM 模型定义（9 张表）
│   │   ├── schemas/                 # Pydantic 数据校验
│   │   │   └── schemas.py           # 请求/响应 Schema
│   │   ├── services/                # 业务逻辑层
│   │   │   ├── llm_client.py        # 双模型 LLM 客户端（Failover）
│   │   │   ├── prompt_builder.py    # 面试 System Prompt 构建器
│   │   │   ├── interview_config.py  # 面试阶段配置加载
│   │   │   ├── interview_config.yaml# 面试阶段 YAML 配置
│   │   │   ├── rag_engine.py        # RAG 检索增强引擎
│   │   │   ├── resume_parser.py     # PDF 简历解析器
│   │   │   ├── evaluator.py         # AI 面试评估引擎
│   │   │   ├── document_processor.py# 文档切片处理器
│   │   │   ├── position_analyzer.py # 岗位分析器
│   │   │   ├── prompt_service.py    # Prompt 模板服务
│   │   │   ├── auth_service.py      # JWT/密码服务
│   │   │   └── audit_service.py     # 审计日志服务
│   │   ├── config.py                # 全局配置（Pydantic Settings）
│   │   └── main.py                  # FastAPI 应用入口
│   ├── init.sql                     # 数据库初始化脚本
│   ├── seed_data.py                 # 题库种子数据（20 道技术题）
│   └── requirements.txt             # Python 依赖
├── frontend/                        # 前端（React + Vite）
│   ├── src/
│   │   ├── components/              # 可复用组件
│   │   │   ├── chart/
│   │   │   │   └── RadarChart.tsx   # ECharts 雷达图
│   │   │   ├── layout/
│   │   │   │   ├── Navbar.tsx       # 顶部导航栏
│   │   │   │   └── ThemeToggle.tsx  # 主题切换按钮
│   │   │   └── ui/
│   │   │       └── Button.tsx       # 通用按钮组件
│   │   ├── pages/                   # 页面组件
│   │   │   ├── Home.tsx             # 首页
│   │   │   ├── Login.tsx            # 登录/注册页
│   │   │   ├── Upload.tsx           # 简历上传页
│   │   │   ├── Interview.tsx        # 面试间（SSE 流式对话）
│   │   │   ├── Report.tsx           # 评估报告页（含历史列表）
│   │   │   └── Admin.tsx            # 管理员后台（5 Tab）
│   │   ├── store/
│   │   │   └── index.ts             # Zustand 全局状态
│   │   ├── types/
│   │   │   └── index.ts             # TypeScript 类型定义
│   │   ├── lib/
│   │   │   └── utils.ts             # 工具函数
│   │   ├── App.tsx                  # 路由配置
│   │   ├── main.tsx                 # 应用入口
│   │   └── index.css                # 全局样式
│   ├── index.html                   # HTML 模板
│   ├── vite.config.ts               # Vite 配置（代理 + 别名）
│   ├── tailwind.config.js           # TailwindCSS 配置
│   ├── tsconfig.json                # TypeScript 配置
│   └── package.json                 # 前端依赖
├── .gitignore                       # Git 忽略规则
└── README.md                        # 项目说明文档
```

---

## 配置说明

### 环境变量一览

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `APP_ENV` | `development` | 运行环境 |
| `DEBUG` | `true` | 调试模式 |
| `MYSQL_HOST` | `localhost` | MySQL 主机 |
| `MYSQL_PORT` | `3306` | MySQL 端口 |
| `MYSQL_USER` | `aceinterviewer` | MySQL 用户名 |
| `MYSQL_PASSWORD` | `aceinterviewer123` | MySQL 密码 |
| `MYSQL_DATABASE` | `aceinterviewer` | 数据库名称 |
| `REDIS_HOST` | `localhost` | Redis 主机 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `JWT_SECRET` | `dev-secret-change-in-production` | JWT 签名密钥（**生产环境必须修改**） |
| `JWT_ALGORITHM` | `HS256` | JWT 算法 |
| `JWT_EXPIRE_MINUTES` | `1440` | Token 有效期（分钟） |
| `DEEPSEEK_API_KEY` | _(空)_ | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek API 地址 |
| `QWEN_API_KEY` | _(空)_ | 通义千问 API Key |
| `QWEN_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 通义千问 DashScope 地址 |
| `QWEN_MODEL_NAME` | `qwen-plus` | 通义千问模型名称 |

### 限流策略

| 路径前缀 | 窗口 | 上限 |
|----------|------|------|
| `/api/interview/chat` | 60 秒 | 15 次 |
| `/api/interview/start` | 60 秒 | 10 次 |
| `/api/auth/*` | 60 秒 | 20 次 |
| `/api/admin/*` | 60 秒 | 200 次 |
| 其他 | 60 秒 | 200 次 |

### 数据库模型（9 张表）

| 表名 | 说明 |
|------|------|
| `users` | 用户（student/admin 角色） |
| `resumes` | 简历（关键词 + 完整文本） |
| `question_bank` | 题库（分类、难度、参考答案） |
| `interview_sessions` | 面试会话（状态、类型、对话历史） |
| `evaluation_reports` | 评估报告（雷达评分 + AI 反馈） |
| `knowledge_documents` | 知识库文档（上传状态、切片计数） |
| `knowledge_chunks` | 知识片段（文档切片内容） |
| `prompt_versions` | Prompt 版本（版本号、内容、激活状态） |
| `prompt_templates` | Prompt 模板（内置/自定义） |
| `audit_logs` | 操作日志（操作人、动作、资源） |

---

## 贡献指南

### 代码规范

- **后端**：遵循 PEP 8，使用 4 空格缩进，函数和类使用 docstring 说明
- **前端**：遵循项目 ESLint 配置，组件使用 PascalCase，工具函数使用 camelCase
- **类型安全**：前端必须通过 TypeScript 类型检查（`npm run build`）
- **无注释原则**：代码自解释，不添加冗余注释（除非逻辑复杂需要说明意图）

### 提交信息格式

```
<type>(<scope>): <subject>

[optional body]
```

**type** 可选值：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具链

**示例**：

```
feat(interview): 添加压力面试类型支持
fix(resume): 修复多列 PDF 简历解析乱序问题
docs(readme): 补充生产环境部署说明
```

### PR 流程

1. Fork 仓库并创建功能分支：`git checkout -b feature/your-feature`
2. 编写代码并测试
3. 确保后端可正常启动、前端 `npm run build` 通过
4. 提交代码并推送到远程：`git push origin feature/your-feature`
5. 创建 Pull Request，描述变更内容和测试方法
6. 等待 Code Review 通过后合并

---

## 许可证

本项目为 **985 大学软件工程专业课程项目**，仅供学习与学术交流使用。

---

## 联系方式与鸣谢

### 鸣谢

- [DeepSeek](https://www.deepseek.com/) - 提供高质量大语言模型 API
- [通义千问 DashScope](https://dashscope.aliyun.com/) - 提供备用模型 API
- [FastAPI](https://fastapi.tiangolo.com/) - 优秀的 Python Web 框架
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) - 现代化前端开发体验
- [TailwindCSS](https://tailwindcss.com/) - 高效的原子化 CSS 框架
- [ECharts](https://echarts.apache.org/) - 强大的数据可视化库

---

<p align="center">
  <strong>AceInterviewer</strong> - 让每一场面试都成为成长的契机
</p>
