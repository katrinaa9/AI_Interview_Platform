from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ===== 用户相关 =====
class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ===== 简历相关 =====
class ResumeUploadResponse(BaseModel):
    id: str
    parsed_keywords: List[str]
    message: str


class ResumeKeywordsRequest(BaseModel):
    keywords: List[str]


# ===== 题库相关 =====
class QuestionCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    question_text: str = Field(..., min_length=1)
    reference_answer: str = Field(..., min_length=1)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class QuestionUpdate(BaseModel):
    """更新题目（所有字段可选，仅更新传入的非 None 字段）"""
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    question_text: Optional[str] = Field(default=None, min_length=1)
    reference_answer: Optional[str] = Field(default=None, min_length=1)
    difficulty: Optional[str] = Field(default=None, pattern="^(easy|medium|hard)$")


class QuestionResponse(BaseModel):
    id: str
    category: str
    question_text: str
    reference_answer: str
    difficulty: str
    times_asked: int = 0
    times_wrong: int = 0
    created_at: datetime


class QuestionListResponse(BaseModel):
    items: List[QuestionResponse]
    total: int
    page: int
    page_size: int


class QuestionStatsItem(BaseModel):
    """高频错题统计项"""
    id: str
    category: str
    question_text: str
    times_asked: int
    times_wrong: int
    error_rate: float  # times_wrong / times_asked


class QuestionStatsResponse(BaseModel):
    items: List[QuestionStatsItem]
    total: int


class QuestionDeleteResponse(BaseModel):
    message: str
    id: str


# ===== 面试相关 =====
class InterviewStartRequest(BaseModel):
    interview_type: str = Field(
        default="technical", pattern="^(technical|pressure|friendly)$"
    )


class InterviewSessionResponse(BaseModel):
    id: str
    status: str
    interview_type: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    welcome_message: Optional[str] = None


class ChatMessageRequest(BaseModel):
    session_id: str
    content: str


class ChatMessageResponse(BaseModel):
    role: str  # "user" | "assistant"
    content: str


# ===== 评估报告相关 =====
class RadarScores(BaseModel):
    tech_depth: int = Field(..., ge=0, le=100, alias="技术深度")
    logic_expression: int = Field(..., ge=0, le=100, alias="逻辑表达")
    expertise: int = Field(..., ge=0, le=100, alias="专业知识")
    adaptability: int = Field(..., ge=0, le=100, alias="应变能力")
    emotional_stability: int = Field(..., ge=0, le=100, alias="情绪稳定性")


class AIFeedback(BaseModel):
    strengths: str = Field(alias="核心优势")
    weaknesses: str = Field(alias="薄弱环节")
    suggestions: str = Field(alias="改进建议")


class EvaluationReportResponse(BaseModel):
    id: str
    session_id: str
    radar_scores: Dict[str, int]
    ai_feedback: Dict[str, str]
    created_at: datetime
    interview_date: Optional[datetime] = None
    interview_duration: Optional[str] = None
    interview_type: Optional[str] = None


# ===== 知识库文档 =====
class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class ChunkResponse(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    content: str
    category: Optional[str] = None
    difficulty: Optional[str] = None
    keywords: Optional[str] = None
    created_at: datetime


class ChunkListResponse(BaseModel):
    items: List[ChunkResponse]
    total: int
    page: int
    page_size: int


class ChunkCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    category: Optional[str] = None
    difficulty: Optional[str] = None
    keywords: Optional[str] = None


class ChunkUpdateRequest(BaseModel):
    content: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    keywords: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    ids: List[str]


# ===== 提示词版本 =====
class PromptVersionResponse(BaseModel):
    id: str
    version_number: int
    content: str
    description: Optional[str] = None
    is_active: bool
    created_by: Optional[str] = None
    created_at: datetime


class PromptVersionListResponse(BaseModel):
    items: List[PromptVersionResponse]
    total: int


class PromptSaveRequest(BaseModel):
    content: str = Field(..., min_length=1)
    description: Optional[str] = None


# ===== 提示词模板 =====
class PromptTemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    content: str
    is_builtin: bool
    created_by: Optional[str] = None
    created_at: datetime


class PromptTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    content: str = Field(..., min_length=1)


class PromptTemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


# ===== 操作日志 =====
class AuditLogResponse(BaseModel):
    id: str
    operator: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[str] = None
    status: str
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int


# ===== 仪表盘统计 =====
class DashboardStatsResponse(BaseModel):
    total_questions: int
    total_documents: int
    total_chunks: int
    today_sessions: int
    week_sessions: int
    month_sessions: int
    total_users: int
    recent_logs: List[AuditLogResponse]