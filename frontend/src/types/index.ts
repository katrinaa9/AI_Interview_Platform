export interface User {
  id: string;
  username: string;
  role: "student" | "admin";
  created_at: string;
}

export interface InterviewSession {
  id: string;
  status: "ongoing" | "completed";
  interview_type: "technical" | "pressure" | "friendly";
  started_at: string;
  ended_at?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type InterviewType = "technical" | "pressure" | "friendly";

export interface RadarScores {
  技术深度: number;
  逻辑表达: number;
  专业知识广度: number;
  应变与解决问题能力: number;
  沟通与协作素养: number;
  项目实践能力: number;
  // 兼容旧版5维度
  专业知识?: number;
  应变能力?: number;
  情绪稳定性?: number;
}

export interface EvidenceFeedbackItem {
  结论: string;
  对话证据: string;
  改进方向: string;
}

export interface AIFeedback {
  总体评价?: string;
  核心优势: string;
  薄弱环节: string;
  详细分析?: string;
  改进建议: string;
  岗位匹配度?: number | string;
  JD匹配亮点?: string;
  JD差距分析?: string;
  岗位补强建议?: string;
  证据化反馈?: EvidenceFeedbackItem[] | string;
}

export interface EvaluationReport {
  id: string;
  session_id: string;
  radar_scores: RadarScores;
  ai_feedback: AIFeedback;
  created_at: string;
  interview_date?: string;
  interview_duration?: string;
  interview_type?: string;
}

export interface ReportHistoryItem {
  session_id: string;
  interview_type: string;
  type_label: string;
  started_at: string | null;
  ended_at: string | null;
  duration: string;
  average_score: number | null;
  has_report: boolean;
}
