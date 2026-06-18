/**
 * SQLite 数据库 — 单例 + 用户表
 */
import initSqlJs, { type Database } from "sql.js";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const DATA_DIR = path.resolve(process.cwd(), "data");
const DB_PATH = path.join(DATA_DIR, "knowledge.db");

let _db: Database | null = null;
let _SQL: any = null;
let _ready = false;

function resolveWasmBinary() {
  const candidates = [
    path.resolve(process.cwd(), "node_modules/.pnpm/sql.js@1.14.1/node_modules/sql.js/dist/sql-wasm.wasm"),
    path.resolve(process.cwd(), "node_modules/sql.js/dist/sql-wasm.wasm"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return fs.readFileSync(p);
  }
  throw new Error("找不到 sql-wasm.wasm 文件");
}

async function getDb(): Promise<Database> {
  if (_db) return _db;
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  const wasmBinary: any = resolveWasmBinary();
  _SQL = await initSqlJs({ wasmBinary });
  _db = new _SQL.Database(fs.existsSync(DB_PATH) ? fs.readFileSync(DB_PATH) : undefined) as Database;
  createTables(_db);
  return _db;
}

function createTables(db: Database) {
  console.log("[db] 建表...", DB_PATH);
  db.run(`
    CREATE TABLE IF NOT EXISTS users (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id         TEXT UNIQUE,
      name            TEXT NOT NULL,
      role            TEXT NOT NULL,
      status          TEXT NOT NULL DEFAULT '正常',
      permission_scope TEXT NOT NULL DEFAULT '全部资料',
      last_login      TEXT NOT NULL,
      account_type    TEXT NOT NULL DEFAULT 'user',
      login_account   TEXT,
      password_hash   TEXT
    );
  `);
  // 迁移旧表
  try { db.run("ALTER TABLE users ADD COLUMN user_id TEXT UNIQUE"); } catch {}
  // 分类表
  db.run(`
    CREATE TABLE IF NOT EXISTS categories (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id     TEXT NOT NULL,
      name        TEXT NOT NULL,
      description TEXT,
      sort_order  INTEGER DEFAULT 0,
      created_at  TEXT NOT NULL,
      updated_at  TEXT NOT NULL,
      UNIQUE(user_id, name)
    );
  `);
  // 种子管理员
  const adminHash = crypto.createHash("sha256").update("Shan1234").digest("hex");
  const adminId = crypto.randomUUID();
  db.run(
    "INSERT OR IGNORE INTO users (user_id, name, role, account_type, login_account, password_hash, status, permission_scope, last_login) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
    [adminId, "管理员", "知识库运营与系统维护", "admin", "admin", adminHash, "正常", "全部资料", new Date().toISOString().slice(0, 10)],
  );
  // 给已有用户补充 user_id
  db.run("UPDATE users SET user_id = ? WHERE (user_id IS NULL OR user_id = '') AND login_account = 'admin'", [adminId]);
}

export function persist() {
  if (!_db) return;
  fs.writeFileSync(DB_PATH, Buffer.from(_db.export()));
}

export async function initDb() {
  if (_ready) return;
  console.log("[db] 初始化数据库...");
  await getDb();
  persist();
  _ready = true;
  console.log("[db] 初始化完成:", DB_PATH);
}

export function queryAll<T = Record<string, unknown>>(sql: string, params: any[] = []): T[] {
  const db = _db!;
  const stmt = db.prepare(sql);
  stmt.bind(params);
  const rows: T[] = [];
  while (stmt.step()) rows.push(stmt.getAsObject() as T);
  stmt.free();
  return rows;
}

export function queryOne<T = Record<string, unknown>>(sql: string, params: any[] = []): T | undefined {
  return queryAll<T>(sql, params)[0];
}

export function execute(sql: string, params: any[] = []) {
  _db!.run(sql, params);
  persist();
}
