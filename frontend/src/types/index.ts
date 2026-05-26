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

export interface AIFeedback {
  总体评价?: string;
  核心优势: string;
  薄弱环节: string;
  详细分析?: string;
  改进建议: string;
}

export interface EvaluationReport {
  id: string;
  session_id: string;
  radar_scores: RadarScores;
  ai_feedback: AIFeedback;
  created_at: string;
  // 面试元数据（直接从API返回）
  interview_date?: string;
  interview_duration?: string;
  interview_type?: string;
}