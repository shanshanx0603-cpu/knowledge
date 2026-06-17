import json
import hashlib
import hmac
import mimetypes
import os
import re
import shutil
import time
import urllib.parse
import uuid
import cgi
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "knowledge_center")
HOST = "127.0.0.1"
PORT = 3000
ADMIN_ACCOUNT = "admin"
ADMIN_PASSWORD = "Shan1234"
DEFAULT_USER_NAME = "刘耀光"
DEFAULT_USER_ACCOUNT = "刘耀光"
DEFAULT_USER_PASSWORD = "liuyaoguang123"
TOKEN_SALT = "knowledge-admin-session"
DEFAULT_CATEGORIES = ["课程资料", "学习资料", "个人资料"]
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


def safe_filename(filename):
    name = Path(filename or "upload.bin").name
    name = re.sub(r"[^\w.\-\u4e00-\u9fff ]+", "_", name, flags=re.UNICODE).strip()
    return name or "upload.bin"


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
        ]
        for column, column_type in resource_migrations:
            if column not in existing_resource_columns:
                conn.execute(f"ALTER TABLE resources ADD COLUMN {column} {column_type}")

        existing_user_columns = {
            row["Field"] for row in conn.execute("SHOW COLUMNS FROM users").fetchall()
        }
        if "account_type" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN account_type VARCHAR(20) NOT NULL DEFAULT 'user'")
        if "login_account" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN login_account VARCHAR(80)")
        if "password_hash" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(128)")

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
        if key not in ("password_hash",)
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


def uploaded_clause(prefix="r"):
    return f" AND {prefix}.stored_path IS NOT NULL AND {prefix}.stored_path <> ''"


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
        "libraries": {
            kb_type: {key: value for key, value in item.items() if key not in ("rawCount", "rawStorage")}
            for kb_type, item in libraries.items()
        },
        "currentUser": public_user(user),
    }


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
                users = [row_to_dict(row) for row in conn.execute("SELECT * FROM users ORDER BY id").fetchall()]
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
        if path == "/api/search":
            return self.search(params)

        return self.serve_static(path)

    def do_POST(self):
        parsed = parse_target(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/login":
            return self.login()
        if parsed.path == "/api/register":
            return self.register()
        if parsed.path == "/api/categories":
            return self.create_category(params)
        if parsed.path == "/api/upload":
            return self.upload_file(params)
        if parsed.path == "/api/knowledge-bases":
            return self.create_knowledge_base()
        if parsed.path == "/api/resources":
            return self.create_resource(params)
        return self.send_json({"error": "接口不存在"}, 404)

    def do_PUT(self):
        parsed = parse_target(self.path)
        if parsed.path.startswith("/api/knowledge-bases/"):
            return self.update_knowledge_base(parsed.path.rsplit("/", 1)[-1])
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
                row = conn.execute(
                    f"SELECT r.knowledge_base_id, r.size_mb FROM resources r WHERE r.id = %s{owner_sql}",
                    [resource_id] + owner_args,
                ).fetchone()
                if row is None:
                    return self.send_json({"error": "资源不存在或无权限删除"}, 404)
                conn.execute("DELETE FROM resources WHERE id = %s", (resource_id,))
                if row is not None:
                    sync_knowledge_base_summary(conn, row["knowledge_base_id"])
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
        if resource is None:
            return self.send_json({"error": "资源不存在或无权限下载"}, 404)
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
        conditions.append("r.stored_path IS NOT NULL AND r.stored_path <> ''")
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
        return self.send_json({"ok": True, "item": created}, 201)

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

    def register(self):
        data = self.read_json()
        username = str(data.get("account", "")).strip()
        password = str(data.get("password", ""))
        if not valid_chinese_username(username):
            return self.send_json({"error": "用户名必须为 2-20 个中文字符"}, 400)
        if not valid_user_password(password):
            return self.send_json({"error": "密码必须为英文+数字组合，且至少 8 个字符"}, 400)

        with connect_db() as conn:
            exists = conn.execute(
                "SELECT id FROM users WHERE login_account = %s OR name = %s",
                (username, username),
            ).fetchone()
            if exists:
                return self.send_json({"error": "该用户名已存在"}, 409)
            conn.execute(
                """
                INSERT INTO users (name, role, account_type, login_account, password_hash, status, permission_scope, last_login)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (username, "普通用户", "user", username, hash_password(password), "正常", "仅本人上传", time.strftime("%Y-%m-%d")),
            )
            user = row_to_dict(
                conn.execute("SELECT * FROM users WHERE login_account = %s", (username,)).fetchone()
            )
        return self.send_json({"ok": True, "user": public_user(user, include_token=True)}, 201)

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

        with connect_db() as conn:
            current_user = self.require_user(conn, params)
            if current_user is None:
                return
            owner = form.getfirst("owner", "").strip() if is_admin(current_user) else ""
            owner = owner or current_user["name"]
            created_at = now_text()
            result = conn.execute(
                """
                INSERT INTO resources
                  (knowledge_base_id, title, content, file_type, size_mb, owner, category, status, status_text, progress, stored_path, mime_type, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    base["id"],
                    title,
                    content,
                    ext,
                    size_mb,
                    owner,
                    category,
                    "indexed",
                    "已索引",
                    100,
                    str(target_path.relative_to(BASE_DIR)),
                    mime_type,
                    created_at,
                    created_at,
                ),
            )
            sync_knowledge_base_summary(conn, base["id"])
        return self.send_json(
            {
                "ok": True,
                "resource": {
                    "id": result.lastrowid,
                    "title": title,
                    "type": kb_type,
                    "file_type": ext,
                    "size_mb": round(size_mb, 3),
                    "owner": owner,
                    "stored_path": str(target_path.relative_to(BASE_DIR)),
                    "mime_type": mime_type,
                },
            },
            201,
        )

    def create_knowledge_base(self):
        data = self.read_json()
        required = ["type", "title", "item_label", "entry"]
        missing = [key for key in required if not data.get(key)]
        if missing:
            return self.send_json({"error": f"缺少字段: {', '.join(missing)}"}, 400)
        with connect_db() as conn:
            conn.execute(
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
        return self.send_json({"ok": True}, 201)

    def update_knowledge_base(self, kb_type):
        data = self.read_json()
        allowed = ["title", "item_label", "count", "storage_gb", "progress", "updated_at", "entry"]
        fields = [field for field in allowed if field in data]
        if not fields:
            return self.send_json({"error": "没有可更新字段"}, 400)
        values = [data[field] for field in fields]
        values.append(kb_type)
        sql = "UPDATE knowledge_bases SET " + ", ".join(f"{field} = %s" for field in fields) + " WHERE type = %s"
        with connect_db() as conn:
            conn.execute(sql, values)
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
            owner = data.get("owner", current_user["name"]) if is_admin(current_user) else current_user["name"]
            conn.execute(
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
        return self.send_json({"ok": True}, 201)


def main():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"知识库系统已启动: http://{HOST}:{PORT}/knowledge-dashboard.html")
    print("按 Ctrl+C 停止服务")
    server.serve_forever()


if __name__ == "__main__":
    main()
