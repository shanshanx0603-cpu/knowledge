import json
import hashlib
import hmac
import mimetypes
import os
import re
import shutil
import time
import urllib.parse
import urllib.error
import urllib.request
import uuid
import cgi
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"


def load_local_env(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env(BASE_DIR / ".env")

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "knowledge_center")
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "")
OSS_UPLOAD_BUCKET = os.getenv("OSS_UPLOAD_BUCKET", "knowledge-center-upload")
OSS_DOWNLOAD_EXPIRES = int(os.getenv("OSS_DOWNLOAD_EXPIRES", "3600"))
RAG_PREPROCESS_BASE_URL = os.getenv("RAG_PREPROCESS_BASE_URL", "http://192.168.2.18:3000").rstrip("/")
RAG_PREPROCESS_TENANT = os.getenv("RAG_PREPROCESS_TENANT", "knowledge")
RAG_PREPROCESS_SOURCE = os.getenv("RAG_PREPROCESS_SOURCE", "knowledge")
RAG_PREPROCESS_BUCKET = os.getenv("RAG_PREPROCESS_BUCKET", "liu-teacher-618-v2")
RAG_PREPROCESS_TIMEOUT = int(os.getenv("RAG_PREPROCESS_TIMEOUT", "8"))
RAG_TRANSCRIBE_MEDIA = os.getenv("RAG_TRANSCRIBE_MEDIA", "false").lower() in {"1", "true", "yes", "on"}
RAG_MEDIA_MODEL = os.getenv("RAG_MEDIA_MODEL", "tiny")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen-plus")
OSS_VECTOR_REGION = os.getenv("OSS_VECTOR_REGION", "cn-hangzhou")
OSS_VECTOR_ENDPOINT = os.getenv("OSS_VECTOR_ENDPOINT", "")
OSS_VECTOR_ACCOUNT_ID = os.getenv("OSS_VECTOR_ACCOUNT_ID", "")
OSS_VECTOR_BUCKET = os.getenv("OSS_VECTOR_BUCKET", RAG_PREPROCESS_BUCKET)
OSS_VECTOR_INDEX = os.getenv("OSS_VECTOR_INDEX", "course")
RAG_SEARCH_TOP_K = int(os.getenv("RAG_SEARCH_TOP_K", "6"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", PUBLIC_BASE_URL)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = 3000
ADMIN_ACCOUNT = "admin"
ADMIN_PASSWORD = "Shan1234"
DEFAULT_USER_NAME = "刘耀光"
DEFAULT_USER_ACCOUNT = "刘耀光"
DEFAULT_USER_PASSWORD = "liuyaoguang123"
TOKEN_SALT = "knowledge-admin-session"
DEFAULT_CATEGORIES = ["课程资料", "学习资料", "个人资料"]
CATEGORY_INDEX_OVERRIDES = {
    "课程资料": "kechengziliao",
    "学习资料": "xuexiziliao",
    "个人资料": "gerenziliao",
}
RAG_INDEX_BY_TYPE = {
    "documents": "course",
    "videos": "video",
    "images": "product",
}
RAG_STATUS_PROGRESS = {
    "pending": 5,
    "manifesting": 15,
    "converting": 35,
    "cleaning": 50,
    "chunking": 68,
    "validating": 82,
    "embedding": 92,
    "completed": 100,
    "failed": 100,
}
RAG_STATUS_TEXT = {
    "pending": "等待RAG回调",
    "manifesting": "下载与清单生成中",
    "converting": "转换Markdown中",
    "cleaning": "清洗中",
    "chunking": "切块中",
    "validating": "校验中",
    "embedding": "向量入库中",
    "completed": "RAG预处理完成",
    "failed": "RAG预处理失败",
}
_DATABASE_READY = False


class DbRow(dict):
    def __init__(self, data, columns):
        super().__init__(data)
        self._columns = columns

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(self._columns[key])
        return super().__getitem__(key)


class QueryResult:
    def __init__(self, cursor):
        self.cursor = cursor
        self.columns = [column[0] for column in cursor.description or []]
        self.rowcount = cursor.rowcount
        self.lastrowid = cursor.lastrowid

    def _row(self, row):
        if row is None:
            return None
        return DbRow(row, self.columns)

    def fetchone(self):
        return self._row(self.cursor.fetchone())

    def fetchall(self):
        return [self._row(row) for row in self.cursor.fetchall()]


class MySQLConnection:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()

    def execute(self, sql, params=None):
        cursor = self.conn.cursor()
        cursor.execute(sql, params or ())
        return QueryResult(cursor)

    def executemany(self, sql, params):
        cursor = self.conn.cursor()
        cursor.executemany(sql, params)
        return QueryResult(cursor)

    def executescript(self, script):
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)


def pymysql_module():
    try:
        import pymysql
        import pymysql.cursors
    except ImportError as exc:
        raise RuntimeError("缺少 PyMySQL，请先运行: python3 -m pip install -r requirements.txt") from exc
    return pymysql


def ensure_database():
    global _DATABASE_READY
    if _DATABASE_READY:
        return
    pymysql = pymysql_module()
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        conn.close()
    _DATABASE_READY = True


def connect_db():
    ensure_database()
    pymysql = pymysql_module()
    return MySQLConnection(
        pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )
    )


def now_text():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def session_token(user):
    source = f"{user.get('login_account', '')}:{user.get('password_hash', '')}:{TOKEN_SALT}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def valid_session(user, token):
    return bool(user and token and hmac.compare_digest(token, session_token(user)))


def valid_chinese_username(username):
    return bool(re.fullmatch(r"[\u4e00-\u9fff]{2,20}", username or ""))


def valid_user_password(password):
    if len(password or "") < 8:
        return False
    return bool(re.search(r"[A-Za-z]", password) and re.search(r"\d", password) and re.fullmatch(r"[A-Za-z\d]+", password))


def oss_enabled():
    return bool(OSS_ACCESS_KEY_ID and OSS_ACCESS_KEY_SECRET and OSS_ENDPOINT)


def oss_module():
    try:
        import oss2
    except ImportError as exc:
        raise RuntimeError("缺少 oss2，请先运行: python3 -m pip install -r requirements.txt") from exc
    return oss2


def oss_auth():
    oss2 = oss_module()
    return oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)


def oss_bucket_client(bucket_name):
    oss2 = oss_module()
    return oss2.Bucket(oss_auth(), OSS_ENDPOINT, bucket_name)


def ensure_upload_bucket():
    if not oss_enabled():
        return ""
    return OSS_UPLOAD_BUCKET


def oss_object_key(stored_name, user_id):
    safe_user_id = re.sub(r"[^0-9A-Za-z_-]", "", str(user_id or "unknown")) or "unknown"
    return f"user-{safe_user_id}_{safe_filename(stored_name)}"


def delete_oss_object(resource):
    if not resource or resource.get("storage_provider") != "oss":
        return
    bucket_name = resource.get("oss_bucket") or ""
    object_key = resource.get("oss_object_key") or ""
    if not bucket_name or not object_key:
        return
    if not oss_enabled():
        raise RuntimeError("OSS 未配置，无法删除远程文件")
    oss_bucket_client(bucket_name).delete_object(object_key)


def rag_index_for_type(kb_type):
    return RAG_INDEX_BY_TYPE.get(kb_type, "course")


def rag_status_payload(status, fallback_text=""):
    status = status or "indexing"
    if status == "completed":
        return "indexed", RAG_STATUS_TEXT["completed"], 100
    if status == "failed":
        return "failed", RAG_STATUS_TEXT["failed"], 100
    return "indexing", RAG_STATUS_TEXT.get(status, fallback_text or "RAG预处理中"), RAG_STATUS_PROGRESS.get(status, 10)


def rag_request(path, method="GET", payload=None):
    url = f"{RAG_PREPROCESS_BASE_URL}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=RAG_PREPROCESS_TIMEOUT) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def require_env(names):
    missing = [name for name in names if not os.getenv(name, "")]
    if missing:
        raise RuntimeError(f"缺少环境变量: {', '.join(missing)}")


def dashscope_request(path, payload, timeout=30):
    require_env(["DASHSCOPE_API_KEY"])
    url = f"https://dashscope.aliyuncs.com/compatible-mode/v1{path}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"DashScope 调用失败: HTTP {exc.code} {detail[:500]}") from exc


def embed_text(text):
    text = str(text or "").strip()
    if not text:
        raise RuntimeError("检索问题不能为空")
    payload = {
        "model": EMBEDDING_MODEL,
        "input": text,
        "encoding_format": "float",
    }
    data = dashscope_request("/embeddings", payload)
    items = data.get("data") or []
    if not items or not items[0].get("embedding"):
        raise RuntimeError("DashScope 未返回 embedding")
    return items[0]["embedding"]


def chat_completion(messages):
    payload = {
        "model": CHAT_MODEL,
        "messages": messages,
        "temperature": 0.2,
    }
    data = dashscope_request("/chat/completions", payload, timeout=60)
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("DashScope 未返回聊天结果")
    return choices[0].get("message", {}).get("content", "").strip()


def oss_vector_client():
    require_env(["OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET", "OSS_VECTOR_ACCOUNT_ID"])
    try:
        import alibabacloud_oss_v2 as oss
        import alibabacloud_oss_v2.vectors as oss_vectors
        from alibabacloud_oss_v2 import credentials
    except ImportError as exc:
        raise RuntimeError("缺少 alibabacloud-oss-v2，请先运行: python3 -m pip install -r requirements.txt") from exc
    provider = credentials.StaticCredentialsProvider(
        os.getenv("OSS_ACCESS_KEY_ID", ""),
        os.getenv("OSS_ACCESS_KEY_SECRET", ""),
        os.getenv("OSS_SESSION_TOKEN") or None,
    )
    config = oss.config.load_default()
    config.region = OSS_VECTOR_REGION
    config.account_id = OSS_VECTOR_ACCOUNT_ID
    config.credentials_provider = provider
    if OSS_VECTOR_ENDPOINT:
        config.endpoint = OSS_VECTOR_ENDPOINT
    return oss_vectors.Client(config), oss_vectors


def vector_query(query, top_k=None, bucket=None, index_name=None, filter_payload=None):
    vector = embed_text(query)
    client, oss_vectors = oss_vector_client()
    result = client.query_vectors(
        oss_vectors.models.QueryVectorsRequest(
            bucket=bucket or OSS_VECTOR_BUCKET,
            index_name=index_name or OSS_VECTOR_INDEX,
            query_vector={"float32": vector},
            filter=filter_payload or None,
            return_distance=True,
            return_metadata=True,
            top_k=int(top_k or RAG_SEARCH_TOP_K),
        )
    )
    return result.vectors or []


def vector_target_for_user(user, requested_bucket="", requested_index="", category=""):
    if is_admin(user):
        bucket = requested_bucket or (user or {}).get("vector_bucket") or OSS_VECTOR_BUCKET
        index_name = requested_index or index_for_category(category)
    else:
        bucket = (user or {}).get("vector_bucket") or default_vector_bucket_for_user(user) or OSS_VECTOR_BUCKET
        index_name = index_for_category(category)
    return {
        "bucket": str(bucket).strip(),
        "index": str(index_name).strip(),
    }


def vector_indexes_for_categories(categories):
    indexes = []
    seen = set()
    for category in categories:
        index_name = index_for_category(category)
        if index_name and index_name not in seen:
            indexes.append(index_name)
            seen.add(index_name)
    return indexes or [OSS_VECTOR_INDEX]


def vector_query_for_target(query, top_k, bucket, index_name, category="", filter_payload=None):
    if category != "__all__":
        return vector_query(query, top_k=top_k, bucket=bucket, index_name=index_name, filter_payload=filter_payload)
    hits = []
    for each_index in vector_indexes_for_categories(DEFAULT_CATEGORIES):
        try:
            for hit in vector_query(query, top_k=top_k, bucket=bucket, index_name=each_index, filter_payload=filter_payload):
                item = dict(hit)
                metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                item["metadata"] = {**metadata, "_vector_index": each_index}
                hits.append(item)
        except Exception:
            continue
    def rank_key(hit):
        distance = hit.get("distance")
        if distance is not None:
            try:
                return (0, float(distance))
            except (TypeError, ValueError):
                pass
        score = hit.get("score")
        if score is not None:
            try:
                return (1, -float(score))
            except (TypeError, ValueError):
                pass
        return (2, 0)
    hits.sort(key=rank_key)
    return hits[:top_k]


def metadata_value(metadata, names, default=""):
    if not isinstance(metadata, dict):
        return default
    for name in names:
        value = metadata.get(name)
        if value is not None and value != "":
            return value
    return default


def clean_source_url(value):
    value = str(value or "").strip()
    if value.startswith(("http://", "https://", "/api/")):
        return value
    return ""


def display_name_from_url(value):
    value = str(value or "").strip()
    if not value.startswith(("http://", "https://")):
        return value
    parsed = urllib.parse.urlparse(value)
    name = Path(urllib.parse.unquote(parsed.path or "")).name
    return name or value


def normalize_vector_hit(hit, resource_lookup=None):
    metadata = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
    resource_id = str(metadata_value(metadata, ["resource_id", "resourceId", "resourceID", "rid"], "") or "")
    resource = resource_lookup.get(resource_id) if resource_lookup and resource_id else None
    title = metadata_value(metadata, ["title", "filename", "file_name", "file", "source_file", "source"], "")
    chunk_text = metadata_value(
        metadata,
        ["chunk_text", "chunkText", "snippet", "text", "content", "page_content", "markdown", "raw_text"],
        "",
    )
    source_url = clean_source_url(metadata_value(metadata, ["source_url", "sourceUrl", "source_file", "sourceFile", "url", "file_url"], ""))
    resource_url = ""
    if resource:
        if resource.get("storage_provider") == "oss" and resource.get("oss_bucket") and resource.get("oss_object_key"):
            endpoint_host = urllib.parse.urlparse(resource.get("oss_endpoint") or OSS_ENDPOINT).netloc
            resource_url = clean_source_url(f"https://{resource['oss_bucket']}.{endpoint_host}/{urllib.parse.quote(resource['oss_object_key'])}")
        elif resource.get("stored_path"):
            resource_url = f"/api/resources/{resource['id']}/download"
    clean_title = (resource or {}).get("title") or display_name_from_url(title) or "未命名片段"
    clean_snippet = str(chunk_text or "").strip()
    if clean_snippet and clean_snippet.startswith("{") and len(clean_snippet) > 800:
        clean_snippet = ""
    score = hit.get("score")
    distance = hit.get("distance")
    return {
        "key": hit.get("key") or hit.get("id") or "",
        "resource_id": resource_id,
        "title": clean_title,
        "snippet": clean_snippet or "该片段缺少正文内容，请检查预处理入库字段。",
        "chunk_text": clean_snippet,
        "source_url": source_url or resource_url,
        "category": metadata_value(metadata, ["category_name", "category"], (resource or {}).get("category", "")),
        "index": metadata_value(metadata, ["_vector_index", "index", "vector_index"], ""),
        "distance": distance,
        "score": score,
        "metadata": metadata,
        "resource": resource,
    }


def visible_resource_lookup(conn, user, resource_ids):
    ids = [str(item) for item in resource_ids if str(item or "").isdigit()]
    if not ids:
        return {}
    owner_sql, owner_args = owner_clause(user, "r")
    placeholders = ", ".join(["%s"] * len(ids))
    rows = conn.execute(
        f"""
        SELECT r.*, k.type AS knowledge_base_type, k.title AS knowledge_base_title
        FROM resources r
        JOIN knowledge_bases k ON k.id = r.knowledge_base_id
        WHERE r.id IN ({placeholders})
        {owner_sql}
        """,
        ids + owner_args,
    ).fetchall()
    return {str(row["id"]): row_to_dict(row) for row in rows}


def build_rag_context(hits, max_chars=6000):
    parts = []
    used = 0
    for idx, hit in enumerate(hits, 1):
        text = (hit.get("chunk_text") or "").strip()
        if not text:
            continue
        source = hit.get("title") or hit.get("key") or f"片段{idx}"
        block = f"[{idx}] 来源：{source}\n{text}"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


def public_source_hit(hit):
    return {
        "key": hit.get("key", ""),
        "resource_id": hit.get("resource_id", ""),
        "title": hit.get("title") or "未命名片段",
        "snippet": hit.get("snippet") or hit.get("chunk_text") or "该片段缺少正文内容，请检查预处理入库字段。",
        "source_url": hit.get("source_url", ""),
        "category": hit.get("category", ""),
        "index": hit.get("index", ""),
        "score": hit.get("score"),
        "distance": hit.get("distance"),
    }


def public_source_hits(hits):
    return [public_source_hit(hit) for hit in hits]


def local_ip_address():
    try:
        import socket
        rag_host = urllib.parse.urlparse(RAG_PREPROCESS_BASE_URL).hostname or "8.8.8.8"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((rag_host, 80))
            return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def callback_base_url():
    base_url = WEBHOOK_BASE_URL.strip().rstrip("/")
    if base_url:
        return base_url
    host = local_ip_address()
    return f"http://{host}:{PORT}"


def rag_webhook_url(resource_id=None):
    path = "/api/rag-preprocess/webhook"
    return f"{callback_base_url()}{path}"


def create_rag_preprocess_task(kb_type, file_urls, resource_id=None, bucket_name="", index_name="", metadata=None):
    if not file_urls:
        return None
    bucket_name = str(bucket_name or RAG_PREPROCESS_BUCKET).strip()
    index_name = str(index_name or rag_index_for_type(kb_type)).strip()
    metadata_payload = {
        "resource_id": str(resource_id or ""),
        "knowledge_base_type": kb_type,
        "owner": bucket_name,
        "category": index_name,
        "index": index_name,
        "source_url": file_urls[0] if len(file_urls) == 1 else "",
        "file_urls": file_urls,
    }
    if isinstance(metadata, dict):
        metadata_payload.update({key: value for key, value in metadata.items() if value is not None})
    payload = {
        "type": "rag-preprocess",
        "tenant": RAG_PREPROCESS_TENANT,
        "source": RAG_PREPROCESS_SOURCE,
        "user_id": str(resource_id or ""),
        "bucket": bucket_name,
        "index": index_name,
        "file_urls": file_urls,
        "callback_url": rag_webhook_url(resource_id),
        "options": {
            "transcribe_media": RAG_TRANSCRIBE_MEDIA,
            "media_model": RAG_MEDIA_MODEL,
        },
        "metadata": metadata_payload,
    }
    return rag_request("/api/rag-preprocess", method="POST", payload=payload)


def update_resource_from_rag_task(conn, resource_id, task):
    if not task:
        return
    rag_status = task.get("status") or "pending"
    status, status_text, progress = rag_status_payload(rag_status)
    summary = task.get("summary") or ""
    conn.execute(
        """
        UPDATE resources
        SET status = %s,
            status_text = %s,
            progress = %s,
            rag_status = %s,
            rag_summary = %s,
            rag_result_json = %s,
            rag_error = %s,
            updated_at = %s
        WHERE id = %s
        """,
        (
            status,
            status_text,
            progress,
            rag_status,
            summary,
            task.get("result_json") or "",
            task.get("error") or "",
            now_text(),
            resource_id,
        ),
    )


def normalize_rag_webhook_payload(data):
    if not isinstance(data, dict):
        return None, "请求体必须是 JSON 对象"
    event = str(data.get("event") or "").strip()
    status = str(data.get("status") or "").strip()
    if event not in {"completed", "failed"}:
        return None, "event 必须为 completed 或 failed"
    if status not in {"completed", "failed"}:
        return None, "status 必须为 completed 或 failed"
    if event != status:
        return None, "event 与 status 不一致"

    summary = data.get("summary")
    result_json = data.get("result_json")
    error = data.get("error")
    if status == "completed":
        if error:
            return None, "completed 回调的 error 必须为空"
        if summary is not None and not isinstance(summary, str):
            return None, "summary 必须为字符串或 null"
        if result_json is not None and not isinstance(result_json, str):
            return None, "result_json 必须为 JSON 字符串或 null"
    if status == "failed":
        if not isinstance(error, str) or not error.strip():
            return None, "failed 回调必须包含 error"
        if summary is not None:
            return None, "failed 回调的 summary 必须为 null"
        if result_json is not None:
            return None, "failed 回调的 result_json 必须为 null"

    return {
        "status": status,
        "summary": summary or "",
        "result_json": result_json or "",
        "error": error or "",
    }, ""


def safe_filename(filename):
    name = Path(filename or "upload.bin").name
    name = re.sub(r"[^\w.\-\u4e00-\u9fff ]+", "_", name, flags=re.UNICODE).strip()
    return name or "upload.bin"


def slugify_pinyin(value, fallback="user"):
    value = str(value or "").strip()
    try:
        from pypinyin import lazy_pinyin
        source = "".join(lazy_pinyin(value))
    except Exception:
        source = value
    slug = re.sub(r"[^a-z0-9]+", "", source.lower())
    return slug or fallback


def default_vector_bucket_for_user(user):
    if not user:
        return OSS_VECTOR_BUCKET
    return slugify_pinyin(user.get("name") or user.get("login_account") or f"user{user.get('id', '')}")


def index_for_category(category, fallback=OSS_VECTOR_INDEX):
    category = str(category or "").strip()
    if not category:
        return fallback
    return CATEGORY_INDEX_OVERRIDES.get(category) or slugify_pinyin(category, fallback)


def ensure_user_vector_targets(conn):
    users = [row_to_dict(row) for row in conn.execute("SELECT * FROM users ORDER BY id").fetchall()]
    for user in users:
        if is_admin(user):
            bucket = user.get("vector_bucket") or OSS_VECTOR_BUCKET
        else:
            bucket = user.get("vector_bucket") or default_vector_bucket_for_user(user)
        conn.execute(
            """
            UPDATE users
            SET vector_bucket = %s,
                vector_index = NULL
            WHERE id = %s
            """,
            (bucket, user["id"]),
        )


def file_extension(filename):
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    return suffix or "bin"


def infer_kb_type(filename, requested_type=""):
    if requested_type in {"documents", "videos", "images"}:
        return requested_type
    ext = file_extension(filename)
    if ext in {"mp4", "mov", "avi", "mkv", "wmv", "flv", "webm", "m4v"}:
        return "videos"
    if ext in {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "tif", "tiff", "heic"}:
        return "images"
    return "documents"


def default_category(kb_type):
    return {
        "documents": "上传文件",
        "videos": "上传视频",
        "images": "上传图片",
    }.get(kb_type, "上传文件")


def sync_knowledge_base_summary(conn, knowledge_base_id=None):
    if knowledge_base_id is None:
        bases = conn.execute("SELECT id FROM knowledge_bases").fetchall()
    else:
        bases = [{"id": knowledge_base_id}]
    for base in bases:
        summary = conn.execute(
            """
            SELECT
              COUNT(*) AS count,
              COALESCE(SUM(size_mb), 0) AS size_mb,
              SUM(CASE WHEN status = 'indexed' THEN 1 ELSE 0 END) AS indexed_count,
              MAX(updated_at) AS updated_at
            FROM resources
            WHERE knowledge_base_id = %s
            """,
            (base["id"],),
        ).fetchone()
        count = int(summary["count"] or 0)
        progress = round(int(summary["indexed_count"] or 0) / count * 100) if count else 0
        conn.execute(
            """
            UPDATE knowledge_bases
            SET `count` = %s,
                storage_gb = %s,
                progress = %s,
                updated_at = COALESCE(%s, updated_at)
            WHERE id = %s
            """,
            (
                count,
                float(summary["size_mb"] or 0) / 1024,
                progress,
                summary["updated_at"],
                base["id"],
            ),
        )


def init_db():
    with connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INT PRIMARY KEY AUTO_INCREMENT,
              name VARCHAR(80) NOT NULL,
              role VARCHAR(120) NOT NULL,
              account_type VARCHAR(20) NOT NULL DEFAULT 'user',
              login_account VARCHAR(80),
              password_hash VARCHAR(128),
              oss_bucket VARCHAR(120),
              vector_bucket VARCHAR(120),
              vector_index VARCHAR(120),
              status VARCHAR(40) NOT NULL DEFAULT '正常',
              permission_scope VARCHAR(80) NOT NULL DEFAULT '全库管理',
              last_login VARCHAR(30) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS knowledge_bases (
              id INT PRIMARY KEY AUTO_INCREMENT,
              type VARCHAR(40) NOT NULL UNIQUE,
              title VARCHAR(120) NOT NULL,
              item_label VARCHAR(40) NOT NULL,
              count INT NOT NULL DEFAULT 0,
              storage_gb DOUBLE NOT NULL DEFAULT 0,
              progress INT NOT NULL DEFAULT 0,
              updated_at VARCHAR(30) NOT NULL,
              entry VARCHAR(80) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS resources (
              id INT PRIMARY KEY AUTO_INCREMENT,
              knowledge_base_id INT NOT NULL,
              title VARCHAR(255) NOT NULL,
              content TEXT NOT NULL,
              file_type VARCHAR(30) NOT NULL,
              size_mb DOUBLE NOT NULL DEFAULT 0,
              owner VARCHAR(80) NOT NULL DEFAULT '刘耀光',
              category VARCHAR(80) NOT NULL DEFAULT '产品文档',
              status VARCHAR(30) NOT NULL DEFAULT 'indexed',
              status_text VARCHAR(40) NOT NULL DEFAULT '已索引',
              progress INT NOT NULL DEFAULT 100,
              stored_path VARCHAR(500),
              mime_type VARCHAR(120),
              storage_provider VARCHAR(20) NOT NULL DEFAULT 'local',
              oss_bucket VARCHAR(120),
              oss_endpoint VARCHAR(200),
              oss_object_key VARCHAR(500),
              rag_task_id VARCHAR(80),
              rag_status VARCHAR(40),
              rag_summary VARCHAR(500),
              rag_result_json TEXT,
              rag_error TEXT,
              created_at VARCHAR(30) NOT NULL,
              updated_at VARCHAR(30) NOT NULL,
              FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS calls (
              id INT PRIMARY KEY AUTO_INCREMENT,
              endpoint VARCHAR(120) NOT NULL,
              created_at VARCHAR(30) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS categories (
              id INT PRIMARY KEY AUTO_INCREMENT,
              name VARCHAR(80) NOT NULL,
              owner VARCHAR(80) NOT NULL DEFAULT '',
              is_default TINYINT NOT NULL DEFAULT 0,
              created_at VARCHAR(30) NOT NULL,
              UNIQUE KEY uniq_category_owner (name, owner)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS operation_logs (
              id INT PRIMARY KEY AUTO_INCREMENT,
              user_name VARCHAR(80) NOT NULL,
              account_type VARCHAR(20) NOT NULL DEFAULT 'user',
              action VARCHAR(60) NOT NULL,
              target_type VARCHAR(60) NOT NULL,
              target_id VARCHAR(80),
              detail VARCHAR(500),
              created_at VARCHAR(30) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
        )

        for category_name in DEFAULT_CATEGORIES:
            exists = conn.execute(
                "SELECT id FROM categories WHERE name = %s AND owner = ''",
                (category_name,),
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO categories (name, owner, is_default, created_at) VALUES (%s, %s, %s, %s)",
                    (category_name, "", 1, now_text()),
                )

        existing_resource_columns = {
            row["Field"] for row in conn.execute("SHOW COLUMNS FROM resources").fetchall()
        }
        resource_migrations = [
            ("owner", "VARCHAR(80) NOT NULL DEFAULT '刘耀光'"),
            ("category", "VARCHAR(80) NOT NULL DEFAULT '产品文档'"),
            ("status_text", "VARCHAR(40) NOT NULL DEFAULT '已索引'"),
            ("progress", "INT NOT NULL DEFAULT 100"),
            ("stored_path", "VARCHAR(500)"),
            ("mime_type", "VARCHAR(120)"),
            ("storage_provider", "VARCHAR(20) NOT NULL DEFAULT 'local'"),
            ("oss_bucket", "VARCHAR(120)"),
            ("oss_endpoint", "VARCHAR(200)"),
            ("oss_object_key", "VARCHAR(500)"),
            ("rag_task_id", "VARCHAR(80)"),
            ("rag_status", "VARCHAR(40)"),
            ("rag_summary", "TEXT"),
            ("rag_result_json", "TEXT"),
            ("rag_error", "TEXT"),
        ]
        for column, column_type in resource_migrations:
            if column not in existing_resource_columns:
                conn.execute(f"ALTER TABLE resources ADD COLUMN {column} {column_type}")
            elif column == "rag_summary":
                conn.execute("ALTER TABLE resources MODIFY COLUMN rag_summary TEXT")

        existing_user_columns = {
            row["Field"] for row in conn.execute("SHOW COLUMNS FROM users").fetchall()
        }
        if "account_type" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN account_type VARCHAR(20) NOT NULL DEFAULT 'user'")
        if "login_account" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN login_account VARCHAR(80)")
        if "password_hash" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(128)")
        if "oss_bucket" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN oss_bucket VARCHAR(120)")
        if "vector_bucket" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN vector_bucket VARCHAR(120)")
        if "vector_index" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN vector_index VARCHAR(120)")

        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            conn.executemany(
                """
                INSERT INTO users (name, role, account_type, login_account, password_hash, status, permission_scope, last_login)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    ("中台管理员", "知识库运营与索引维护", "admin", ADMIN_ACCOUNT, hash_password(ADMIN_PASSWORD), "正常", "全库管理", "2026-06-15"),
                    (DEFAULT_USER_NAME, "普通用户", "user", DEFAULT_USER_ACCOUNT, hash_password(DEFAULT_USER_PASSWORD), "正常", "仅本人上传", "2026-06-15"),
                ],
            )
        else:
            admin_exists = conn.execute("SELECT id FROM users WHERE name = '中台管理员'").fetchone()
            if not admin_exists:
                conn.execute(
                    """
                    INSERT INTO users (name, role, account_type, login_account, password_hash, status, permission_scope, last_login)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    ("中台管理员", "知识库运营与索引维护", "admin", ADMIN_ACCOUNT, hash_password(ADMIN_PASSWORD), "正常", "全库管理", "2026-06-15"),
                )
            conn.execute(
                """
                UPDATE users
                SET account_type = 'admin',
                    role = '知识库运营与索引维护',
                    login_account = %s,
                    password_hash = %s,
                    permission_scope = '全库管理'
                WHERE name = '中台管理员'
                """,
                (ADMIN_ACCOUNT, hash_password(ADMIN_PASSWORD)),
            )
            conn.execute("DELETE FROM users WHERE name IN ('张三', '李四', '王五')")
            user_exists = conn.execute("SELECT id FROM users WHERE name = %s", (DEFAULT_USER_NAME,)).fetchone()
            if not user_exists:
                conn.execute(
                    """
                    INSERT INTO users (name, role, account_type, login_account, password_hash, status, permission_scope, last_login)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (DEFAULT_USER_NAME, "普通用户", "user", DEFAULT_USER_ACCOUNT, hash_password(DEFAULT_USER_PASSWORD), "正常", "仅本人上传", "2026-06-15"),
                )
            else:
                conn.execute(
                    """
                    UPDATE users
                    SET account_type = 'user',
                        role = '普通用户',
                        login_account = %s,
                        password_hash = %s,
                        permission_scope = '仅本人上传'
                    WHERE name = %s
                    """,
                    (DEFAULT_USER_ACCOUNT, hash_password(DEFAULT_USER_PASSWORD), DEFAULT_USER_NAME),
                )
            conn.execute("UPDATE resources SET owner = %s WHERE owner IN ('张三', '李四', '王五')", (DEFAULT_USER_NAME,))

        ensure_user_vector_targets(conn)

        kb_count = conn.execute("SELECT COUNT(*) FROM knowledge_bases").fetchone()[0]
        if kb_count == 0:
            seeds = [
                ("documents", "文档知识库", "文档", 8462, 128.7, 94, "2024-05-21 14:30", "文档检索"),
                ("videos", "视频知识库", "视频", 326, 256.4, 97, "2024-05-21 14:45", "视频解析"),
                ("images", "图片知识库", "图片", 1284, 96.3, 92, "2024-05-21 14:20", "图片识别"),
            ]
            conn.executemany(
                """
                INSERT INTO knowledge_bases
                  (type, title, item_label, count, storage_gb, progress, updated_at, entry)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                seeds,
            )

            kb_ids = {
                row["type"]: row["id"]
                for row in conn.execute("SELECT id, type FROM knowledge_bases").fetchall()
            }
            resources = [
                (kb_ids["documents"], "产品需求文档 PRD 3.0.pdf", "产品需求、功能范围、业务流程与验收标准。", "pdf", 24.8, DEFAULT_USER_NAME, "产品文档", "indexed", "已索引", 100, "2024-05-21 14:30"),
                (kb_ids["documents"], "用户手册_v2.1.docx", "用户手册、功能说明、常见问题与操作指南。", "docx", 15.6, DEFAULT_USER_NAME, "使用手册", "indexed", "已索引", 100, "2024-05-21 11:15"),
                (kb_ids["documents"], "系统设计方案.pdf", "系统架构、模块设计、接口方案与部署说明。", "pdf", 8.2, DEFAULT_USER_NAME, "技术文档", "indexed", "已索引", 100, "2024-05-21 10:05"),
                (kb_ids["documents"], "项目周报 2024-05-20.pptx", "项目进度、风险同步、阶段计划与周报总结。", "pptx", 6.5, "赵六", "周报总结", "indexed", "已索引", 100, "2024-05-21 09:20"),
                (kb_ids["documents"], "接口文档说明.docx", "API 接口、字段说明、错误码与联调规范。", "docx", 12.3, DEFAULT_USER_NAME, "技术文档", "indexing", "索引中", 68, "2024-05-21 09:10"),
                (kb_ids["documents"], "数据安全规范.pdf", "数据安全、权限管理、脱敏规则与审计要求。", "pdf", 5.4, "孙七", "安全规范", "failed", "失败", 0, "2024-05-21 08:50"),
                (kb_ids["documents"], "培训资料_新员工入职指南.docx", "新人入职流程、培训计划、工具账号与规范。", "docx", 18.7, DEFAULT_USER_NAME, "培训资料", "indexed", "已索引", 100, "2024-05-21 08:30"),
                (kb_ids["documents"], "AI 大模型应用实践.pdf", "大模型场景、知识库增强、提示词与案例实践。", "pdf", 31.2, DEFAULT_USER_NAME, "AI 研究", "indexed", "已索引", 100, "2024-05-21 07:45"),
                (kb_ids["documents"], "版本更新说明 v1.2.docx", "版本变更、功能优化、缺陷修复与升级说明。", "docx", 3.8, DEFAULT_USER_NAME, "版本管理", "indexed", "已索引", 100, "2024-05-20 17:30"),
                (kb_ids["documents"], "运维操作手册.pdf", "运维流程、监控告警、故障处理与发布规范。", "pdf", 9.6, "赵六", "运维文档", "indexing", "索引中", 32, "2024-05-20 16:20"),
                (kb_ids["videos"], "新人培训视频", "知识库中台使用、标签规范、检索演示。", "mp4", 824.0, DEFAULT_USER_NAME, "培训资料", "indexed", "已索引", 100, "2024-05-21 14:45"),
                (kb_ids["videos"], "销冠案例复盘", "优秀案例拆解、关键对话节点与成交策略。", "mp4", 512.3, DEFAULT_USER_NAME, "案例复盘", "indexed", "已索引", 100, "2024-05-21 13:20"),
                (kb_ids["images"], "产品海报素材", "营销海报、视觉物料、活动图片资产。", "png", 96.3, DEFAULT_USER_NAME, "视觉素材", "indexed", "已索引", 100, "2024-05-21 14:20"),
                (kb_ids["images"], "课程封面图库", "课程封面、讲师照片、宣传图。", "jpg", 64.8, "孙七", "视觉素材", "indexed", "已索引", 100, "2024-05-21 12:10"),
            ]
            conn.executemany(
                """
                INSERT INTO resources
                  (knowledge_base_id, title, content, file_type, size_mb, owner, category, status, status_text, progress, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [(kb, title, content, ft, size, owner, category, status, status_text, progress, updated, updated) for kb, title, content, ft, size, owner, category, status, status_text, progress, updated in resources],
            )

            conn.executemany(
                "INSERT INTO calls (endpoint, created_at) VALUES (%s, %s)",
                [("/api/search", now_text()) for _ in range(128000)],
            )

        ensure_document_samples(conn)
        ensure_media_samples(conn)
        sync_knowledge_base_summary(conn)


def ensure_document_samples(conn):
    doc_base = conn.execute("SELECT id FROM knowledge_bases WHERE type = 'documents'").fetchone()
    if doc_base is None:
        return

    samples = [
        ("产品需求文档 PRD 3.0.pdf", "产品需求、功能范围、业务流程与验收标准。", "pdf", 24.8, DEFAULT_USER_NAME, "产品文档", "indexed", "已索引", 100, "2024-05-21 14:30"),
        ("用户手册_v2.1.docx", "用户手册、功能说明、常见问题与操作指南。", "docx", 15.6, DEFAULT_USER_NAME, "使用手册", "indexed", "已索引", 100, "2024-05-21 11:15"),
        ("系统设计方案.pdf", "系统架构、模块设计、接口方案与部署说明。", "pdf", 8.2, DEFAULT_USER_NAME, "技术文档", "indexed", "已索引", 100, "2024-05-21 10:05"),
        ("项目周报 2024-05-20.pptx", "项目进度、风险同步、阶段计划与周报总结。", "pptx", 6.5, "赵六", "周报总结", "indexed", "已索引", 100, "2024-05-21 09:20"),
        ("接口文档说明.docx", "API 接口、字段说明、错误码与联调规范。", "docx", 12.3, DEFAULT_USER_NAME, "技术文档", "indexing", "索引中", 68, "2024-05-21 09:10"),
        ("数据安全规范.pdf", "数据安全、权限管理、脱敏规则与审计要求。", "pdf", 5.4, "孙七", "安全规范", "failed", "失败", 0, "2024-05-21 08:50"),
        ("培训资料_新员工入职指南.docx", "新人入职流程、培训计划、工具账号与规范。", "docx", 18.7, DEFAULT_USER_NAME, "培训资料", "indexed", "已索引", 100, "2024-05-21 08:30"),
        ("AI 大模型应用实践.pdf", "大模型场景、知识库增强、提示词与案例实践。", "pdf", 31.2, DEFAULT_USER_NAME, "AI 研究", "indexed", "已索引", 100, "2024-05-21 07:45"),
        ("版本更新说明 v1.2.docx", "版本变更、功能优化、缺陷修复与升级说明。", "docx", 3.8, DEFAULT_USER_NAME, "版本管理", "indexed", "已索引", 100, "2024-05-20 17:30"),
        ("运维操作手册.pdf", "运维流程、监控告警、故障处理与发布规范。", "pdf", 9.6, "赵六", "运维文档", "indexing", "索引中", 32, "2024-05-20 16:20"),
    ]

    for title, content, file_type, size_mb, owner, category, status, status_text, progress, updated_at in samples:
        exists = conn.execute("SELECT id FROM resources WHERE title = %s", (title,)).fetchone()
        if exists:
            conn.execute(
                """
                UPDATE resources
                SET owner = %s, category = %s, status = %s, status_text = %s, progress = %s, updated_at = %s
                WHERE id = %s
                """,
                (owner, category, status, status_text, progress, updated_at, exists["id"]),
            )
            continue
        conn.execute(
            """
            INSERT INTO resources
              (knowledge_base_id, title, content, file_type, size_mb, owner, category, status, status_text, progress, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (doc_base["id"], title, content, file_type, size_mb, owner, category, status, status_text, progress, updated_at, updated_at),
        )


def ensure_media_samples(conn):
    bases = {
        row["type"]: row["id"]
        for row in conn.execute("SELECT id, type FROM knowledge_bases WHERE type IN ('videos', 'images')").fetchall()
    }
    samples = [
        ("videos", "新人培训视频.mp4", "知识库中台使用、标签规范、检索演示。", "mp4", 824.0, DEFAULT_USER_NAME, "培训资料", "indexed", "已索引", 100, "2024-05-21 14:45"),
        ("videos", "销冠案例复盘.mp4", "优秀案例拆解、关键对话节点与成交策略。", "mp4", 512.3, DEFAULT_USER_NAME, "案例复盘", "indexed", "已索引", 100, "2024-05-21 13:20"),
        ("videos", "产品演示录屏.mov", "核心功能演示、使用路径和客户讲解口径。", "mov", 426.7, DEFAULT_USER_NAME, "产品演示", "indexed", "已索引", 100, "2024-05-21 11:40"),
        ("videos", "直播回放 2024-05-20.mp4", "线上直播课程回放和问答环节。", "mp4", 1024.5, "赵六", "直播回放", "indexing", "索引中", 62, "2024-05-21 10:30"),
        ("videos", "客户访谈片段.mp4", "客户需求、使用反馈和典型异议处理。", "mp4", 318.2, "孙七", "客户案例", "failed", "失败", 0, "2024-05-21 09:15"),
        ("videos", "内部培训精剪.mp4", "培训重点片段、知识点拆解和复习材料。", "mp4", 268.9, DEFAULT_USER_NAME, "培训资料", "indexed", "已索引", 100, "2024-05-20 17:20"),
        ("images", "产品海报素材.png", "营销海报、视觉物料、活动图片资产。", "png", 96.3, DEFAULT_USER_NAME, "视觉素材", "indexed", "已索引", 100, "2024-05-21 14:20"),
        ("images", "课程封面图库.jpg", "课程封面、讲师照片、宣传图。", "jpg", 64.8, "孙七", "视觉素材", "indexed", "已索引", 100, "2024-05-21 12:10"),
        ("images", "讲师形象照.png", "讲师头像、半身照和宣传图。", "png", 42.1, DEFAULT_USER_NAME, "人物素材", "indexed", "已索引", 100, "2024-05-21 11:30"),
        ("images", "活动现场照片.jpg", "活动现场、签到、互动和合影照片。", "jpg", 118.6, "赵六", "活动素材", "indexing", "索引中", 58, "2024-05-21 10:15"),
        ("images", "界面截图合集.png", "产品界面、流程截图和功能标注。", "png", 73.4, DEFAULT_USER_NAME, "产品截图", "indexed", "已索引", 100, "2024-05-20 18:00"),
        ("images", "旧版物料归档.jpg", "历史宣传物料与旧版设计稿。", "jpg", 36.2, DEFAULT_USER_NAME, "归档素材", "failed", "失败", 0, "2024-05-20 16:45"),
    ]
    for kb_type, title, content, file_type, size_mb, owner, category, status, status_text, progress, updated_at in samples:
        if kb_type not in bases:
            continue
        exists = conn.execute("SELECT id FROM resources WHERE title = %s", (title,)).fetchone()
        if exists:
            conn.execute(
                """
                UPDATE resources
                SET owner = %s, category = %s, status = %s, status_text = %s, progress = %s, updated_at = %s
                WHERE id = %s
                """,
                (owner, category, status, status_text, progress, updated_at, exists["id"]),
            )
            continue
        conn.execute(
            """
            INSERT INTO resources
              (knowledge_base_id, title, content, file_type, size_mb, owner, category, status, status_text, progress, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (bases[kb_type], title, content, file_type, size_mb, owner, category, status, status_text, progress, updated_at, updated_at),
        )


def row_to_dict(row):
    return dict(row) if row is not None else None


def public_user(user, include_token=False):
    if user is None:
        return None
    public = {
        key: value
        for key, value in user.items()
        if key not in ("password_hash", "vector_index")
    }
    if include_token:
        public["sessionToken"] = session_token(user)
    return public


def public_users(users):
    return [public_user(user) for user in users]


def parse_target(target):
    try:
        target = target.encode("latin-1").decode("utf-8")
    except UnicodeError:
        pass
    return urllib.parse.urlparse(target)


def format_count(value):
    value = int(value)
    if value >= 10000:
      return f"{value / 10000:.1f}万"
    return f"{value:,}"


def get_current_user(conn, params):
    requested = params.get("user", [""])[0]
    token = params.get("token", [""])[0]
    if not requested or not token:
        return None
    user = row_to_dict(conn.execute("SELECT * FROM users WHERE name = %s", (requested,)).fetchone())
    if not valid_session(user, token):
        return None
    return user


def is_admin(user):
    return (user or {}).get("account_type") == "admin"


def owner_clause(user, prefix="r"):
    if is_admin(user):
        return "", []
    return f" AND {prefix}.owner = %s", [user["name"]]


def log_operation(conn, user, action, target_type, target_id=None, detail=""):
    if user is None:
        return
    conn.execute(
        """
        INSERT INTO operation_logs (user_name, account_type, action, target_type, target_id, detail, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            user.get("name", ""),
            user.get("account_type", "user"),
            action,
            target_type,
            str(target_id or ""),
            str(detail or "")[:500],
            now_text(),
        ),
    )


def uploaded_clause(prefix="r"):
    return f" AND (({prefix}.stored_path IS NOT NULL AND {prefix}.stored_path <> '') OR ({prefix}.storage_provider = 'oss' AND {prefix}.oss_object_key IS NOT NULL AND {prefix}.oss_object_key <> ''))"


def visible_base_payload(conn, base, user):
    owner_sql, owner_args = owner_clause(user, "r")
    rows = conn.execute(
        f"""
        SELECT r.status, r.size_mb, r.updated_at
        FROM resources r
        WHERE r.knowledge_base_id = %s
        {uploaded_clause("r")}
        {owner_sql}
        """,
        [base["id"]] + owner_args,
    ).fetchall()
    count = len(rows)
    storage_gb = sum(float(row["size_mb"] or 0) for row in rows) / 1024
    indexed_count = sum(1 for row in rows if row["status"] == "indexed")
    progress = round(indexed_count / count * 100) if count else 0
    updated = max((row["updated_at"] for row in rows), default=base["updated_at"])
    return {
        "id": base["id"],
        "title": base["title"],
        "label": base["item_label"],
        "count": f"{count:,}",
        "rawCount": count,
        "storage": f"{storage_gb:.1f} GB",
        "rawStorage": storage_gb,
        "progress": progress,
        "updated": updated,
        "entry": base["entry"],
    }


def scoped_base_dict(conn, base, user):
    item = row_to_dict(base)
    owner_sql, owner_args = owner_clause(user, "r")
    summary = conn.execute(
        f"""
        SELECT
          COUNT(*) AS count,
          COALESCE(SUM(r.size_mb), 0) AS size_mb,
          SUM(CASE WHEN r.status = 'indexed' THEN 1 ELSE 0 END) AS indexed_count,
          MAX(r.updated_at) AS updated_at
        FROM resources r
        WHERE r.knowledge_base_id = %s
        {uploaded_clause("r")}
        {owner_sql}
        """,
        [base["id"]] + owner_args,
    ).fetchone()
    count = int(summary["count"] or 0)
    item["count"] = count
    item["storage_gb"] = round(float(summary["size_mb"] or 0) / 1024, 1)
    item["progress"] = round(int(summary["indexed_count"] or 0) / count * 100) if count else 0
    item["updated_at"] = summary["updated_at"] or item["updated_at"]
    return item


def dashboard_payload(user=None):
    with connect_db() as conn:
        bases = [row_to_dict(row) for row in conn.execute("SELECT * FROM knowledge_bases ORDER BY id").fetchall()]
        call_count = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        libraries = {
            base["type"]: visible_base_payload(conn, base, user)
            for base in bases
        }
        total_storage = sum(float(item["rawStorage"]) for item in libraries.values())
        avg_progress = round(sum(int(item["progress"]) for item in libraries.values()) / max(len(libraries), 1))
        owner_sql, owner_args = owner_clause(user, "r")
        category_count = conn.execute(
            f"""
            SELECT COUNT(DISTINCT r.category) AS count
            FROM resources r
            WHERE 1 = 1
            {uploaded_clause("r")}
            {owner_sql}
            """,
            owner_args,
        ).fetchone()[0]
        if user and not is_admin(user):
            today_new = conn.execute(
                f"SELECT COUNT(*) FROM resources WHERE owner = %s {uploaded_clause('resources')} AND DATE(created_at) = CURDATE()",
                (user["name"],),
            ).fetchone()[0]
        else:
            today_new = conn.execute(
                f"SELECT COUNT(*) FROM resources WHERE 1 = 1 {uploaded_clause('resources')} AND DATE(created_at) = CURDATE()"
            ).fetchone()[0]
        owner_sql_for_resources, owner_args_for_resources = owner_clause(user, "r")
        resource_rows = conn.execute(
            f"""
            SELECT r.status, r.size_mb, r.created_at
            FROM resources r
            WHERE 1 = 1
            {uploaded_clause("r")}
            {owner_sql_for_resources}
            """,
            owner_args_for_resources,
        ).fetchall()

    total_resources = len(resource_rows)
    indexed = sum(1 for row in resource_rows if row["status"] == "indexed")
    indexing = sum(1 for row in resource_rows if row["status"] == "indexing")
    failed = sum(1 for row in resource_rows if row["status"] == "failed")
    pending = max(total_resources - indexed - indexing - failed, 0)
    task_progress = round(indexed / total_resources * 100) if total_resources else 0

    today = datetime.date.today()
    trend = []
    for offset in range(6, -1, -1):
        day = today - datetime.timedelta(days=offset)
        day_text = day.strftime("%Y-%m-%d")
        count = sum(1 for row in resource_rows if str(row["created_at"] or "").startswith(day_text))
        trend.append({
            "date": day.strftime("%m-%d"),
            "count": count,
        })
    weekly_total = sum(item["count"] for item in trend)
    daily_average = round(weekly_total / 7) if trend else 0

    return {
        "stats": {
            "totalKnowledgeBases": len(bases),
            "memoryUsage": min(99, round(total_storage / 6.7)),
            "memoryText": f"使用 {total_storage:.1f}GB / 650.0GB",
            "todayNew": today_new,
            "indexRate": avg_progress,
            "calls": format_count(call_count),
            "callGrowth": "18.6%",
            "categoryCount": int(category_count or 0),
        },
        "overview": {
            "totalResources": total_resources,
            "storageGb": round(total_storage, 1),
            "tasks": {
                "indexed": indexed,
                "indexing": indexing,
                "failed": failed,
                "pending": pending,
                "progress": task_progress,
            },
            "trend": {
                "days": trend,
                "total": weekly_total,
                "average": daily_average,
            },
        },
        "libraries": {
            kb_type: {key: value for key, value in item.items() if key not in ("rawCount", "rawStorage")}
            for kb_type, item in libraries.items()
        },
        "currentUser": public_user(user),
    }


class FastThreadingHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def require_user(self, conn, params):
        user = get_current_user(conn, params)
        if user is None:
            self.send_json({"error": "请先登录"}, 401)
            return None
        return user

    def do_GET(self):
        parsed = parse_target(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/api/health":
            return self.send_json({"ok": True, "time": now_text()})
        if path == "/api/dashboard":
            with connect_db() as conn:
                current_user = self.require_user(conn, params)
                if current_user is None:
                    return
            return self.send_json(dashboard_payload(current_user))
        if path == "/api/profile":
            with connect_db() as conn:
                current_user = get_current_user(conn, params)
                if current_user is not None and is_admin(current_user):
                    users = [row_to_dict(row) for row in conn.execute("SELECT * FROM users ORDER BY id").fetchall()]
                elif current_user is not None:
                    users = [current_user]
                else:
                    users = []
            return self.send_json({"user": public_user(current_user), "users": public_users(users)})
        if path == "/api/knowledge-bases":
            with connect_db() as conn:
                rows = [row_to_dict(row) for row in conn.execute("SELECT * FROM knowledge_bases ORDER BY id").fetchall()]
            return self.send_json({"items": rows})
        if path.startswith("/api/knowledge-bases/"):
            kb_type = path.rsplit("/", 1)[-1]
            return self.get_knowledge_base(kb_type, params)
        resource_download_match = re.match(r"^/api/resources/(\d+)/download$", path)
        if resource_download_match:
            return self.download_resource(resource_download_match.group(1), params)
        if path == "/api/resources":
            return self.list_resources(params)
        if path == "/api/categories":
            return self.list_categories(params)
        if path == "/api/operation-logs":
            return self.list_operation_logs(params)
        if path == "/api/search":
            return self.search(params)

        return self.serve_static(path)

    def do_POST(self):
        parsed = parse_target(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/login":
            return self.login()
        if parsed.path == "/api/users":
            return self.create_user(params)
        if parsed.path == "/api/categories":
            return self.create_category(params)
        if parsed.path == "/api/upload":
            return self.upload_file(params)
        if parsed.path == "/api/rag-preprocess/webhook":
            return self.rag_preprocess_webhook(params)
        if parsed.path == "/api/rag-search":
            return self.rag_search(params)
        if parsed.path == "/api/chat":
            return self.chat(params)
        if parsed.path == "/api/knowledge-bases":
            return self.create_knowledge_base(params)
        if parsed.path == "/api/resources":
            return self.create_resource(params)
        return self.send_json({"error": "接口不存在"}, 404)

    def do_PUT(self):
        parsed = parse_target(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path.startswith("/api/knowledge-bases/"):
            return self.update_knowledge_base(parsed.path.rsplit("/", 1)[-1], params)
        return self.send_json({"error": "接口不存在"}, 404)

    def do_DELETE(self):
        parsed = parse_target(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path.startswith("/api/resources/"):
            resource_id = parsed.path.rsplit("/", 1)[-1]
            with connect_db() as conn:
                current_user = self.require_user(conn, params)
                if current_user is None:
                    return
                owner_sql, owner_args = owner_clause(current_user, "r")
                row = row_to_dict(conn.execute(
                    f"SELECT r.* FROM resources r WHERE r.id = %s{owner_sql}",
                    [resource_id] + owner_args,
                ).fetchone())
                if row is None:
                    return self.send_json({"error": "资源不存在或无权限删除"}, 404)
                try:
                    delete_oss_object(row)
                except Exception as exc:
                    return self.send_json({"error": f"OSS 文件删除失败：{exc}"}, 500)
                conn.execute("DELETE FROM resources WHERE id = %s", (resource_id,))
                if row is not None:
                    sync_knowledge_base_summary(conn, row["knowledge_base_id"])
                log_operation(conn, current_user, "delete", "resource", resource_id, "删除文件资源")
            return self.send_json({"ok": True})
        return self.send_json({"error": "接口不存在"}, 404)

    def do_HEAD(self):
        parsed = parse_target(self.path)
        path = parsed.path
        if path == "/":
            path = "/knowledge-dashboard.html"
        safe_path = Path(urllib.parse.unquote(path.lstrip("/")))
        file_path = (BASE_DIR / safe_path).resolve()
        if not str(file_path).startswith(str(BASE_DIR)) or not file_path.exists() or file_path.is_dir():
            self.send_response(404)
            self.end_headers()
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.end_headers()

    def serve_static(self, path):
        if path == "/":
            path = "/knowledge-dashboard.html"
        safe_path = Path(urllib.parse.unquote(path.lstrip("/")))
        file_path = (BASE_DIR / safe_path).resolve()
        if not str(file_path).startswith(str(BASE_DIR)) or not file_path.exists() or file_path.is_dir():
            return self.send_json({"error": "资源不存在"}, 404)

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def download_resource(self, resource_id, params):
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            owner_sql, owner_args = owner_clause(current_user, "r")
            resource = row_to_dict(
                conn.execute(
                    f"SELECT r.* FROM resources r WHERE r.id = %s{owner_sql}",
                    [resource_id] + owner_args,
                ).fetchone()
            )
            if resource is not None:
                log_operation(conn, current_user, "download", "resource", resource_id, resource.get("title", ""))
        if resource is None:
            return self.send_json({"error": "资源不存在或无权限下载"}, 404)
        if resource.get("storage_provider") == "oss":
            if not oss_enabled():
                return self.send_json({"error": "OSS 未配置，无法下载该文件"}, 500)
            bucket_name = resource.get("oss_bucket") or ""
            object_key = resource.get("oss_object_key") or ""
            if not bucket_name or not object_key:
                return self.send_json({"error": "OSS 文件信息不完整"}, 404)
            bucket = oss_bucket_client(bucket_name)
            signed_url = bucket.sign_url("GET", object_key, OSS_DOWNLOAD_EXPIRES)
            self.send_response(302)
            self.send_header("Location", signed_url)
            self.end_headers()
            return
        if not resource.get("stored_path"):
            return self.send_json({"error": "该记录没有可下载的上传文件"}, 404)

        file_path = (BASE_DIR / resource["stored_path"]).resolve()
        upload_root = UPLOAD_DIR.resolve()
        if not str(file_path).startswith(str(upload_root)) or not file_path.exists() or file_path.is_dir():
            return self.send_json({"error": "文件不存在"}, 404)

        content_type = resource.get("mime_type") or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        download_name = resource.get("title") or file_path.name
        encoded_name = urllib.parse.quote(download_name)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
        self.end_headers()
        with file_path.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def get_knowledge_base(self, kb_type, params):
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            base = row_to_dict(conn.execute("SELECT * FROM knowledge_bases WHERE type = %s", (kb_type,)).fetchone())
            if base is None:
                return self.send_json({"error": "知识库不存在"}, 404)
            owner_sql, owner_args = owner_clause(current_user, "r")
            resources = [
                row_to_dict(row)
                for row in conn.execute(
                    f"""
                    SELECT r.* FROM resources r
                    WHERE r.knowledge_base_id = %s
                    {uploaded_clause("r")}
                    {owner_sql}
                    ORDER BY r.updated_at DESC
                    """,
                    [base["id"]] + owner_args,
                ).fetchall()
            ]
            scoped_base = scoped_base_dict(conn, base, current_user)
        return self.send_json({"item": scoped_base, "resources": resources, "currentUser": public_user(current_user)})

    def list_resources(self, params):
        kb_type = params.get("type", [""])[0]
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            owner_sql, owner_args = owner_clause(current_user, "r")

        sql = """
            SELECT r.*, k.type AS knowledge_base_type, k.title AS knowledge_base_title
            FROM resources r
            JOIN knowledge_bases k ON k.id = r.knowledge_base_id
        """
        args = []
        conditions = []
        conditions.append("((r.stored_path IS NOT NULL AND r.stored_path <> '') OR (r.storage_provider = 'oss' AND r.oss_object_key IS NOT NULL AND r.oss_object_key <> ''))")
        if kb_type:
            conditions.append("k.type = %s")
            args.append(kb_type)
        if owner_sql:
            conditions.append(owner_sql.replace(" AND ", "", 1))
            args.extend(owner_args)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY r.updated_at DESC"
        with connect_db() as conn:
            rows = [row_to_dict(row) for row in conn.execute(sql, args).fetchall()]
        return self.send_json({"items": rows, "currentUser": public_user(current_user)})

    def search(self, params):
        query = params.get("q", [""])[0].strip()
        like = f"%{query}%"
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            owner_sql, owner_args = owner_clause(current_user, "r")
            conn.execute("INSERT INTO calls (endpoint, created_at) VALUES (%s, %s)", ("/api/search", now_text()))
            log_operation(conn, current_user, "search", "resource", "", query)
            if query:
                rows = [
                    row_to_dict(row)
                    for row in conn.execute(
                        f"""
                        SELECT r.*, k.type AS knowledge_base_type, k.title AS knowledge_base_title
                        FROM resources r
                        JOIN knowledge_bases k ON k.id = r.knowledge_base_id
                        WHERE (r.title LIKE %s OR r.content LIKE %s OR k.title LIKE %s)
                        {uploaded_clause("r")}
                        {owner_sql}
                        ORDER BY r.updated_at DESC
                        """,
                        [like, like, like] + owner_args,
                    ).fetchall()
                ]
            else:
                rows = []
        return self.send_json({"query": query, "items": rows, "currentUser": public_user(current_user)})

    def rag_search(self, params):
        data = self.read_json()
        query = str(data.get("query") or data.get("message") or "").strip()
        top_k = int(data.get("top_k") or data.get("topK") or RAG_SEARCH_TOP_K)
        top_k = max(1, min(top_k, 20))
        requested_bucket = str(data.get("bucket") or "").strip()
        requested_index = str(data.get("index") or data.get("index_name") or "").strip()
        category = str(data.get("category") or "").strip()
        filter_payload = data.get("filter") if isinstance(data.get("filter"), dict) else None
        if not query:
            return self.send_json({"error": "请输入检索问题"}, 400)
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            target = vector_target_for_user(current_user, requested_bucket, requested_index, category)
            bucket = target["bucket"]
            index_name = target["index"]
            try:
                raw_hits = vector_query_for_target(query, top_k, bucket, index_name, category, filter_payload)
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 500)
            metadata_ids = [
                metadata_value(hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}, ["resource_id", "resourceId", "resourceID", "rid"], "")
                for hit in raw_hits
            ]
            resource_lookup = visible_resource_lookup(conn, current_user, metadata_ids)
            hits = []
            for raw_hit in raw_hits:
                hit = normalize_vector_hit(raw_hit, resource_lookup)
                if hit.get("resource_id") and hit["resource_id"] not in resource_lookup:
                    continue
                hits.append(hit)
            log_operation(conn, current_user, "rag_search", "vector", "", query)
        return self.send_json({
            "query": query,
            "bucket": bucket,
            "index": index_name,
            "hits": public_source_hits(hits),
            "currentUser": public_user(current_user),
        })

    def chat(self, params):
        data = self.read_json()
        message = str(data.get("message") or data.get("query") or "").strip()
        if not message:
            return self.send_json({"error": "请输入对话内容"}, 400)
        history = data.get("history") if isinstance(data.get("history"), list) else []
        top_k = int(data.get("top_k") or data.get("topK") or RAG_SEARCH_TOP_K)
        top_k = max(1, min(top_k, 12))
        requested_bucket = str(data.get("bucket") or "").strip()
        requested_index = str(data.get("index") or data.get("index_name") or "").strip()
        category = str(data.get("category") or "").strip()
        filter_payload = data.get("filter") if isinstance(data.get("filter"), dict) else None
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            target = vector_target_for_user(current_user, requested_bucket, requested_index, category)
            bucket = target["bucket"]
            index_name = target["index"]
            try:
                raw_hits = vector_query_for_target(message, top_k, bucket, index_name, category, filter_payload)
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 500)
            metadata_ids = [
                metadata_value(hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}, ["resource_id", "resourceId", "resourceID", "rid"], "")
                for hit in raw_hits
            ]
            resource_lookup = visible_resource_lookup(conn, current_user, metadata_ids)
            hits = []
            for raw_hit in raw_hits:
                hit = normalize_vector_hit(raw_hit, resource_lookup)
                if hit.get("resource_id") and hit["resource_id"] not in resource_lookup:
                    continue
                hits.append(hit)
            context = build_rag_context(hits)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是知识库中台的AI助手。请优先基于给定知识库片段回答；"
                        "如果片段不足以回答，请明确说明资料中没有足够依据。"
                        "回答要简洁，并在涉及资料结论时标注引用编号，如[1]。"
                    ),
                }
            ]
            for item in history[-8:]:
                role = item.get("role")
                content = str(item.get("content") or "").strip()
                if role in {"user", "assistant"} and content:
                    messages.append({"role": role, "content": content[:2000]})
            messages.append({
                "role": "user",
                "content": f"知识库片段：\n{context or '未召回到可用片段。'}\n\n用户问题：{message}",
            })
            try:
                answer = chat_completion(messages)
            except Exception as exc:
                return self.send_json({"error": str(exc), "sources": public_source_hits(hits)}, 500)
            conn.execute("INSERT INTO calls (endpoint, created_at) VALUES (%s, %s)", ("/api/chat", now_text()))
            log_operation(conn, current_user, "chat", "vector", "", message)
        return self.send_json({
            "answer": answer,
            "sources": public_source_hits(hits),
            "bucket": bucket,
            "index": index_name,
            "currentUser": public_user(current_user),
        })

    def list_operation_logs(self, params):
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            if is_admin(current_user):
                rows = conn.execute(
                    "SELECT * FROM operation_logs ORDER BY id DESC LIMIT 200"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM operation_logs WHERE user_name = %s ORDER BY id DESC LIMIT 200",
                    (current_user["name"],),
                ).fetchall()
        return self.send_json({
            "items": [row_to_dict(row) for row in rows],
            "currentUser": public_user(current_user),
        })

    def list_categories(self, params):
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            owner_sql, owner_args = owner_clause(current_user, "r")
            category_rows = conn.execute(
                """
                SELECT * FROM categories
                WHERE owner = '' OR owner = %s
                ORDER BY is_default DESC, id ASC
                """,
                (current_user["name"],),
            ).fetchall()
            category_names = [row["name"] for row in category_rows]
            rows = conn.execute(
                f"""
                SELECT r.category, COUNT(*) AS count
                FROM resources r
                WHERE r.category IN ({", ".join(["%s"] * max(1, len(category_names)))})
                {uploaded_clause("r")}
                {owner_sql}
                GROUP BY r.category
                """,
                (category_names or [""]) + owner_args,
            ).fetchall()
        counts = {row["category"]: int(row["count"] or 0) for row in rows}
        return self.send_json({
            "items": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "count": counts.get(row["name"], 0),
                    "isDefault": bool(row["is_default"]),
                    "owner": row["owner"],
                }
                for row in category_rows
            ],
            "currentUser": public_user(current_user),
        })

    def create_category(self, params):
        data = self.read_json()
        name = str(data.get("name", "")).strip()
        if not re.fullmatch(r"[\w\u4e00-\u9fff ]{2,20}", name or "", flags=re.UNICODE):
            return self.send_json({"error": "分类名称需为 2-20 个中文、英文、数字或空格"}, 400)
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            owner = "" if is_admin(current_user) else current_user["name"]
            default_exists = conn.execute(
                "SELECT id FROM categories WHERE name = %s AND owner = ''",
                (name,),
            ).fetchone()
            if default_exists:
                return self.send_json({"error": "该分类已存在"}, 409)
            user_exists = conn.execute(
                "SELECT id FROM categories WHERE name = %s AND owner = %s",
                (name, owner),
            ).fetchone()
            if user_exists:
                return self.send_json({"error": "该分类已存在"}, 409)
            conn.execute(
                "INSERT INTO categories (name, owner, is_default, created_at) VALUES (%s, %s, %s, %s)",
                (name, owner, 0, now_text()),
            )
            created = row_to_dict(
                conn.execute(
                    "SELECT * FROM categories WHERE name = %s AND owner = %s",
                    (name, owner),
                ).fetchone()
            )
            log_operation(conn, current_user, "create_category", "category", created["id"], name)
        return self.send_json({"ok": True, "item": created}, 201)

    def rag_preprocess_webhook(self, params):
        data = self.read_json()
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        resource_id = (
            data.get("resource_id")
            or data.get("resourceId")
            or metadata.get("resource_id")
            or ""
        )
        task_id = data.get("task_id") or data.get("id") or data.get("taskId") or ""
        if not resource_id and not task_id:
            return self.send_json({"error": "缺少 resource_id 或 task_id"}, 400)

        task, validation_error = normalize_rag_webhook_payload(data)
        if validation_error:
            return self.send_json({"ok": False, "error": validation_error}, 400)
        with connect_db() as conn:
            resource = None
            if task_id:
                resource = row_to_dict(conn.execute("SELECT * FROM resources WHERE rag_task_id = %s", (task_id,)).fetchone())
            if resource is None and resource_id:
                resource = row_to_dict(conn.execute("SELECT * FROM resources WHERE id = %s", (resource_id,)).fetchone())
            if resource is None:
                return self.send_json({"error": "未找到对应资源"}, 404)
            if task_id and not resource.get("rag_task_id"):
                conn.execute("UPDATE resources SET rag_task_id = %s WHERE id = %s", (task_id, resource["id"]))
            update_resource_from_rag_task(conn, resource["id"], task)
            log_operation(
                conn,
                {"name": "RAG回调", "account_type": "system"},
                "rag_webhook",
                "resource",
                resource["id"],
                f"{task.get('status')} / {task_id}",
            )
        return self.send_json({"ok": True})

    def login(self):
        data = self.read_json()
        account = str(data.get("account", "")).strip()
        password = str(data.get("password", ""))
        with connect_db() as conn:
            user = row_to_dict(
                conn.execute(
                    "SELECT * FROM users WHERE login_account = %s",
                    (account,),
                ).fetchone()
            )
            if user is None or not hmac.compare_digest(user.get("password_hash") or "", hash_password(password)):
                return self.send_json({"error": "账号或密码错误"}, 401)
            conn.execute(
                "UPDATE users SET last_login = %s WHERE id = %s",
                (time.strftime("%Y-%m-%d"), user["id"]),
            )
            user["last_login"] = time.strftime("%Y-%m-%d")
        return self.send_json({"ok": True, "user": public_user(user, include_token=True)})

    def create_user(self, params):
        data = self.read_json()
        username = str(data.get("account", "")).strip()
        password = str(data.get("password", ""))
        if not valid_chinese_username(username):
            return self.send_json({"error": "用户名必须为 2-20 个中文字符"}, 400)
        if not valid_user_password(password):
            return self.send_json({"error": "密码必须为英文+数字组合，且至少 8 个字符"}, 400)

        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            if not is_admin(current_user):
                return self.send_json({"error": "仅管理员可以分配账号"}, 403)
            exists = conn.execute(
                "SELECT id FROM users WHERE login_account = %s OR name = %s",
                (username, username),
            ).fetchone()
            if exists:
                return self.send_json({"error": "该用户名已存在"}, 409)
            vector_bucket = default_vector_bucket_for_user({"name": username, "login_account": username})
            conn.execute(
                """
                INSERT INTO users (name, role, account_type, login_account, password_hash, vector_bucket, status, permission_scope, last_login)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (username, "普通用户", "user", username, hash_password(password), vector_bucket, "正常", "仅本人上传", time.strftime("%Y-%m-%d")),
            )
            user = row_to_dict(
                conn.execute("SELECT * FROM users WHERE login_account = %s", (username,)).fetchone()
            )
            log_operation(conn, current_user, "create_user", "user", user["id"], username)
        return self.send_json({"ok": True, "user": public_user(user)}, 201)

    def upload_file(self, params):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return self.send_json({"error": "请使用 multipart/form-data 上传文件"}, 400)

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )
        file_item = form["file"] if "file" in form else None
        if file_item is None or not getattr(file_item, "filename", ""):
            return self.send_json({"error": "请选择要上传的文件"}, 400)

        original_name = safe_filename(file_item.filename)
        kb_type = infer_kb_type(original_name, form.getfirst("type", ""))
        ext = file_extension(original_name)
        title = form.getfirst("title", "").strip() or original_name
        category = form.getfirst("category", "").strip() or DEFAULT_CATEGORIES[0]
        content = form.getfirst("description", "").strip() or f"上传文件：{original_name}"

        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            category_exists = conn.execute(
                """
                SELECT id FROM categories
                WHERE name = %s AND (owner = '' OR owner = %s)
                """,
                (category, current_user["name"]),
            ).fetchone()
            if not category_exists:
                return self.send_json({"error": "请选择有效分类"}, 400)
            base = conn.execute("SELECT id FROM knowledge_bases WHERE type = %s", (kb_type,)).fetchone()
            if base is None:
                return self.send_json({"error": "知识库不存在"}, 404)

        stored_name = f"{time.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}_{original_name}"
        target_dir = UPLOAD_DIR / kb_type
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / stored_name
        with target_path.open("wb") as output:
            shutil.copyfileobj(file_item.file, output)

        size_mb = target_path.stat().st_size / 1024 / 1024
        mime_type = file_item.type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        storage_provider = "local"
        oss_bucket_name = ""
        oss_endpoint = ""
        oss_key = ""
        oss_url = ""
        rag_task_id = ""
        rag_status = ""
        rag_summary = ""
        rag_result_json = ""
        rag_error = ""
        stored_path = str(target_path.relative_to(BASE_DIR))

        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            owner = form.getfirst("owner", "").strip() if is_admin(current_user) else ""
            owner = owner or current_user["name"]
            if oss_enabled():
                try:
                    oss_bucket_name = ensure_upload_bucket()
                    oss_key = oss_object_key(stored_name, current_user["id"])
                    bucket = oss_bucket_client(oss_bucket_name)
                    bucket.put_object_from_file(oss_key, str(target_path))
                    storage_provider = "oss"
                    oss_endpoint = OSS_ENDPOINT
                    oss_url = f"https://{oss_bucket_name}.{urllib.parse.urlparse(OSS_ENDPOINT).netloc}/{urllib.parse.quote(oss_key)}"
                    stored_path = ""
                    target_path.unlink()
                except Exception as exc:
                    return self.send_json({"error": f"OSS 上传失败：{exc}"}, 500)
                rag_status = "pending"
                rag_summary = RAG_STATUS_TEXT["pending"]
            status, status_text, progress = rag_status_payload(rag_status, "已索引") if rag_status else ("indexed", "已索引", 100)
            created_at = now_text()
            result = conn.execute(
                """
                INSERT INTO resources
                  (knowledge_base_id, title, content, file_type, size_mb, owner, category, status, status_text, progress, stored_path, mime_type, storage_provider, oss_bucket, oss_endpoint, oss_object_key, rag_task_id, rag_status, rag_summary, rag_result_json, rag_error, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    base["id"],
                    title,
                    content,
                    ext,
                    size_mb,
                    owner,
                    category,
                    status,
                    rag_summary or status_text,
                    progress,
                    stored_path,
                    mime_type,
                    storage_provider,
                    oss_bucket_name,
                    oss_endpoint,
                    oss_key,
                    rag_task_id,
                    rag_status,
                    rag_summary,
                    rag_result_json,
                    rag_error,
                    created_at,
                    created_at,
                ),
            )
            sync_knowledge_base_summary(conn, base["id"])
            resource_id = result.lastrowid
            if oss_url:
                try:
                    vector_user = row_to_dict(
                        conn.execute("SELECT * FROM users WHERE name = %s", (owner,)).fetchone()
                    ) or current_user
                    vector_target = vector_target_for_user(vector_user, category=category)
                    rag_task = create_rag_preprocess_task(
                        kb_type,
                        [oss_url],
                        resource_id,
                        bucket_name=vector_target["bucket"],
                        index_name=vector_target["index"],
                        metadata={
                            "title": title,
                            "filename": original_name,
                            "source_file": oss_url,
                            "source_url": oss_url,
                            "category_name": category,
                            "index": vector_target["index"],
                            "bucket": vector_target["bucket"],
                            "owner": owner,
                            "mime_type": mime_type,
                            "file_type": ext,
                        },
                    )
                    rag_task_id = rag_task.get("task_id") or rag_task.get("id") or ""
                    rag_status = rag_task.get("status") or "pending"
                    rag_summary = rag_task.get("summary") or RAG_STATUS_TEXT.get(rag_status, "RAG任务已提交")
                    status, status_text, progress = rag_status_payload(rag_status)
                    conn.execute(
                        """
                        UPDATE resources
                        SET status = %s,
                            status_text = %s,
                            progress = %s,
                            rag_task_id = %s,
                            rag_status = %s,
                            rag_summary = %s,
                            rag_error = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        (
                            status,
                            rag_summary or status_text,
                            progress,
                            rag_task_id,
                            rag_status,
                            rag_summary,
                            "",
                            now_text(),
                            resource_id,
                        ),
                    )
                except Exception as exc:
                    rag_status = "pending"
                    rag_error = str(exc)
                    status, status_text, progress = rag_status_payload(rag_status, "RAG任务提交中")
                    conn.execute(
                        """
                        UPDATE resources
                        SET status = %s,
                            status_text = %s,
                            progress = %s,
                            rag_status = %s,
                            rag_error = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        (status, status_text, progress, rag_status, rag_error, now_text(), resource_id),
                    )
            log_operation(
                conn,
                current_user,
                "upload",
                "resource",
                resource_id,
                oss_url or f"{title} / {category}",
            )
        return self.send_json(
            {
                "ok": True,
                "resource": {
                    "id": resource_id,
                    "title": title,
                    "type": kb_type,
                    "file_type": ext,
                    "size_mb": round(size_mb, 3),
                    "owner": owner,
                    "stored_path": stored_path,
                    "mime_type": mime_type,
                    "storage_provider": storage_provider,
                    "oss_bucket": oss_bucket_name,
                    "oss_object_key": oss_key,
                    "url": oss_url,
                    "rag_task_id": rag_task_id,
                    "rag_status": rag_status,
                    "rag_summary": rag_summary,
                    "rag_error": rag_error,
                },
            },
            201,
        )

    def create_knowledge_base(self, params):
        data = self.read_json()
        required = ["type", "title", "item_label", "entry"]
        missing = [key for key in required if not data.get(key)]
        if missing:
            return self.send_json({"error": f"缺少字段: {', '.join(missing)}"}, 400)
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            if not is_admin(current_user):
                return self.send_json({"error": "仅管理员可新增知识库"}, 403)
            result = conn.execute(
                """
                INSERT INTO knowledge_bases
                  (type, title, item_label, count, storage_gb, progress, updated_at, entry)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    data["type"],
                    data["title"],
                    data["item_label"],
                    int(data.get("count", 0)),
                    float(data.get("storage_gb", 0)),
                    int(data.get("progress", 0)),
                    data.get("updated_at", now_text()),
                    data["entry"],
                ),
            )
            log_operation(conn, current_user, "create_knowledge_base", "knowledge_base", result.lastrowid, data["title"])
        return self.send_json({"ok": True}, 201)

    def update_knowledge_base(self, kb_type, params):
        data = self.read_json()
        allowed = ["title", "item_label", "count", "storage_gb", "progress", "updated_at", "entry"]
        fields = [field for field in allowed if field in data]
        if not fields:
            return self.send_json({"error": "没有可更新字段"}, 400)
        values = [data[field] for field in fields]
        values.append(kb_type)
        sql = "UPDATE knowledge_bases SET " + ", ".join(f"{field} = %s" for field in fields) + " WHERE type = %s"
        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            if not is_admin(current_user):
                return self.send_json({"error": "仅管理员可修改知识库"}, 403)
            conn.execute(sql, values)
            log_operation(conn, current_user, "update_knowledge_base", "knowledge_base", kb_type, ",".join(fields))
        return self.send_json({"ok": True})

    def create_resource(self, params):
        data = self.read_json()
        kb_type = data.get("type")
        title = data.get("title")
        content = data.get("content", "")
        if not kb_type or not title:
            return self.send_json({"error": "缺少 type 或 title"}, 400)
        with connect_db() as conn:
            base = conn.execute("SELECT id FROM knowledge_bases WHERE type = %s", (kb_type,)).fetchone()
            if base is None:
                return self.send_json({"error": "知识库不存在"}, 404)
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            if not is_admin(current_user):
                return self.send_json({"error": "请通过上传文件新增资源"}, 403)
            owner = data.get("owner", current_user["name"]) if is_admin(current_user) else current_user["name"]
            result = conn.execute(
                """
                INSERT INTO resources
                  (knowledge_base_id, title, content, file_type, size_mb, owner, category, status, status_text, progress, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    base["id"],
                    title,
                    content,
                    data.get("file_type", "txt"),
                    float(data.get("size_mb", 0)),
                    owner,
                    data.get("category", "产品文档"),
                    data.get("status", "indexed"),
                    data.get("status_text", "已索引"),
                    int(data.get("progress", 100)),
                    now_text(),
                    now_text(),
                ),
            )
            conn.execute(
                """
                UPDATE knowledge_bases
                SET count = count + 1,
                    storage_gb = storage_gb + %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (float(data.get("size_mb", 0)) / 1024, now_text(), base["id"]),
            )
            sync_knowledge_base_summary(conn, base["id"])
            log_operation(conn, current_user, "create_resource", "resource", result.lastrowid, title)
        return self.send_json({"ok": True}, 201)


def main():
    init_db()
    server = FastThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"知识库系统已启动: http://{HOST}:{PORT}/knowledge-dashboard.html")
    print("按 Ctrl+C 停止服务")
    server.serve_forever()


if __name__ == "__main__":
    main()
