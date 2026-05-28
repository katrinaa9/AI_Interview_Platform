import re
import logging
import fitz
from pathlib import Path
from app.models.database import async_session
from app.models.models import KnowledgeDocument, KnowledgeChunk

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads/documents")
MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

MIN_CHUNK_LENGTH = 50

_QA_BOUNDARY_PATTERNS = [
    re.compile(r"\n\s*(?:Q|问|题目|Question|问题)\s*[：:.\d)]", re.IGNORECASE),
    re.compile(r"\n\s*\d{1,3}\s*[.、)]\s*", re.IGNORECASE),
    re.compile(r"\n\s*(?:##+)\s+", re.IGNORECASE),
    re.compile(r"\n\s*(?:答|Answer|A)\s*[：:]\s*\n", re.IGNORECASE),
    re.compile(r"\n\s*[-—]{3,}\s*\n"),
]

_TECH_KEYWORDS: dict[str, list[str]] = {
    "React": ["react", "jsx", "hooks", "usestate", "useeffect", "component", "virtual dom", "redux", "zustand"],
    "Vue": ["vue", "vuex", "pinia", "v-for", "v-if", "composition api", "vue3", "vue2"],
    "TypeScript": ["typescript", "interface", "generic", "type alias", "ts", "类型系统"],
    "JavaScript": ["javascript", "es6", "promise", "async", "closure", "prototype", "event loop", "js"],
    "Python": ["python", "django", "flask", "fastapi", "pip", "asyncio", "numpy", "pandas"],
    "Java": ["java", "spring", "jvm", "maven", "gradle", "springboot", "mybatis"],
    "MySQL": ["mysql", "sql", "index", "query", "join", "transaction", "innodb", "b+树"],
    "Redis": ["redis", "cache", "pub/sub", "sorted set", "hash", "string", "list"],
    "Docker": ["docker", "container", "kubernetes", "k8s", "compose", "image"],
    "Linux": ["linux", "shell", "bash", "systemd", "cron", "进程", "线程", "文件权限"],
    "Network": ["tcp", "http", "dns", "socket", "websocket", "https", "ssl", "tls", "osi"],
    "Algorithm": ["algorithm", "data structure", "sort", "binary tree", "dynamic programming", "bfs", "dfs", "哈希", "链表", "二叉树"],
    "Design Pattern": ["design pattern", "singleton", "factory", "observer", "strategy", "设计模式"],
    "Git": ["git", "commit", "branch", "merge", "rebase", "pull request"],
    "CI/CD": ["ci/cd", "jenkins", "github actions", "gitlab ci", "deployment", "pipeline"],
}


def validate_file(filename: str, file_size: int) -> tuple[bool, str]:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"不支持的文件类型: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}"
    if file_size > MAX_FILE_SIZE:
        return False, f"文件过大: {file_size / 1024 / 1024:.1f}MB，限制为 50MB"
    return True, ""


def extract_text(file_path: str, file_type: str) -> str:
    if file_type == "pdf":
        doc = fitz.open(file_path)
        pages = [page.get_text(sort=True) for page in doc]
        doc.close()
        return "\n".join(pages)
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


def _find_qa_boundaries(text: str) -> list[int]:
    boundaries: list[int] = set()
    for pattern in _QA_BOUNDARY_PATTERNS:
        for match in pattern.finditer(text):
            boundaries.add(match.start())
    return sorted(boundaries)


def split_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())

    qa_boundaries = _find_qa_boundaries(text)
    if qa_boundaries:
        segments: list[str] = []
        prev = 0
        for boundary in qa_boundaries:
            if boundary > prev:
                segments.append(text[prev:boundary].strip())
            prev = boundary
        if prev < len(text):
            segments.append(text[prev:].strip())
        
        chunks: list[str] = []
        for segment in segments:
            if not segment:
                continue
            
            if _is_valid_chunk(segment):
                if len(segment) > chunk_size:
                    chunks.extend(_split_long_segment(segment, chunk_size, overlap))
                else:
                    chunks.append(segment)
            elif len(segment) > MIN_CHUNK_LENGTH // 2:
                chunks.append(segment)
    else:
        paragraphs = re.split(r"\n\n+", text)
        segments = [p.strip() for p in paragraphs if p.strip()]

        chunks = []
        current = ""

        for segment in segments:
            if not segment:
                continue

            if len(current) + len(segment) + 1 <= chunk_size:
                current = f"{current}\n{segment}" if current else segment
            else:
                if current and _is_valid_chunk(current):
                    chunks.append(current.strip())

                if len(segment) > chunk_size:
                    chunks.extend(_split_long_segment(segment, chunk_size, overlap))
                    current = ""
                else:
                    current = segment

        if current and _is_valid_chunk(current):
            chunks.append(current.strip())

    return chunks


def _split_long_segment(text: str, chunk_size: int, overlap: int) -> list[str]:
    result: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            boundary = text.rfind("\n", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary
        piece = text[start:end].strip()
        if _is_valid_chunk(piece):
            result.append(piece)
        start = end - overlap
        if start >= len(text):
            break
    return result


def _is_valid_chunk(text: str) -> bool:
    text = text.strip()
    if len(text) < MIN_CHUNK_LENGTH:
        return False
    non_whitespace = re.sub(r"\s+", "", text)
    if len(non_whitespace) < MIN_CHUNK_LENGTH // 2:
        return False
    chinese_or_alpha = re.findall(r"[一-龥a-zA-Z]", text)
    if len(chinese_or_alpha) < 10:
        return False
    return True


def detect_category(content: str) -> str:
    lower = content.lower()
    matched: list[str] = []
    for tech, keywords in _TECH_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            matched.append(tech)
    if matched:
        return "、".join(matched[:3])
    return "General"


def detect_difficulty(content: str) -> str:
    hard_signals = ["底层原理", "源码", "优化策略", "架构设计", "分布式", "高并发", "性能调优", "源码分析", "内核"]
    easy_signals = ["什么是", "简单介绍", "基本概念", "入门", "初学者"]
    if any(s in content for s in hard_signals):
        return "hard"
    if any(s in content for s in easy_signals):
        return "easy"
    return "medium"


async def process_document(document_id: str, file_path: str, file_type: str):
    try:
        async with async_session() as db:
            doc = await db.get(KnowledgeDocument, document_id)
            if not doc:
                return

            doc.status = "processing"
            await db.commit()

            text = extract_text(file_path, file_type)
            if not text.strip():
                doc.status = "failed"
                doc.error_message = "文档内容为空或无法提取文本"
                await db.commit()
                return

            chunks = split_chunks(text)

            if not chunks:
                doc.status = "failed"
                doc.error_message = "文档内容过短或无法生成有效知识片段"
                await db.commit()
                return

            for idx, chunk_text in enumerate(chunks):
                category = detect_category(chunk_text)
                difficulty = detect_difficulty(chunk_text)
                chunk = KnowledgeChunk(
                    document_id=document_id,
                    chunk_index=idx,
                    content=chunk_text,
                    category=category,
                    difficulty=difficulty,
                    keywords=category,
                )
                db.add(chunk)

            doc.chunk_count = len(chunks)
            doc.status = "completed"
            await db.commit()
            logger.info(f"文档处理完成: {doc.filename} → {len(chunks)} chunks (原始文本 {len(text)} 字符)")

    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        async with async_session() as db:
            doc = await db.get(KnowledgeDocument, document_id)
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)[:500]
                await db.commit()
