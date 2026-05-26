-- AceInterviewer Database Initialization
-- 初始化数据库表结构

CREATE DATABASE IF NOT EXISTS aceinterviewer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE aceinterviewer;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id CHAR(36) PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'admin') NOT NULL DEFAULT 'student',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 简历表
CREATE TABLE IF NOT EXISTS resumes (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    parsed_keywords JSON,
    raw_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 题库表
CREATE TABLE IF NOT EXISTS question_bank (
    id CHAR(36) PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    question_text TEXT NOT NULL,
    reference_answer TEXT NOT NULL,
    difficulty ENUM('easy', 'medium', 'hard') DEFAULT 'medium',
    times_asked INT DEFAULT 0 COMMENT '被抽取次数',
    times_wrong INT DEFAULT 0 COMMENT '回答错误次数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_difficulty (difficulty)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 面试会话表
CREATE TABLE IF NOT EXISTS interview_sessions (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    status ENUM('ongoing', 'completed') NOT NULL DEFAULT 'ongoing',
    interview_type ENUM('technical', 'pressure', 'friendly') NOT NULL DEFAULT 'technical',
    dialogue_history JSON,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 评估报告表
CREATE TABLE IF NOT EXISTS evaluation_reports (
    id CHAR(36) PRIMARY KEY,
    session_id CHAR(36) NOT NULL,
    radar_scores JSON NOT NULL,
    ai_feedback JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES interview_sessions(id) ON DELETE CASCADE,
    UNIQUE INDEX idx_session_id (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;