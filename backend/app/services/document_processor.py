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

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


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
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages)
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


def split_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = re.split(r"\n\n+", text)

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 1 <= chunk_size:
            current = f"{current}\n{para}" if current else para
        else:
            if current:
                chunks.append(current.strip())
            if len(para) > chunk_size:
                words = para
                while len(words) > chunk_size:
                    chunks.append(words[:chunk_size].strip())
                    words = words[chunk_size - overlap:]
                current = words
            else:
                current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def detect_category(content: str) -> str:
    tech_map = {
        "React": ["react", "jsx", "hooks", "usestate", "useeffect", "component"],
        "Vue": ["vue", "vuex", "pinia", "v-for", "v-if", "composition api"],
        "TypeScript": ["typescript", "interface", "generic", "type alias"],
        "JavaScript": ["javascript", "es6", "promise", "async", "closure"],
        "Python": ["python", "django", "flask", "fastapi", "pip"],
        "Java": ["java", "spring", "jvm", "maven", "gradle"],
        "MySQL": ["mysql", "sql", "index", "query", "join", "transaction"],
        "Redis": ["redis", "cache", "pub/sub", "sorted set"],
        "Docker": ["docker", "container", "kubernetes", "k8s"],
        "Linux": ["linux", "shell", "bash", "systemd", "cron"],
        "Network": ["tcp", "http", "dns", "socket", "websocket"],
        "Algorithm": ["algorithm", "data structure", "sort", "binary tree", "dynamic programming"],
    }
    lower = content.lower()
    for tech, keywords in tech_map.items():
        if any(kw in lower for kw in keywords):
            return tech
    return "General"


def detect_difficulty(content: str) -> str:
    hard_signals = ["底层原理", "源码", "优化策略", "架构设计", "分布式", "高并发", "性能调优"]
    easy_signals = ["什么是", "简单介绍", "基本概念", "入门"]
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
            logger.info(f"文档处理完成: {doc.filename} → {len(chunks)} chunks")

    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        async with async_session() as db:
            doc = await db.get(KnowledgeDocument, document_id)
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)[:500]
                await db.commit()
