-- SQLite 全量数据库表结构定义与初始化脚本

CREATE TABLE IF NOT EXISTS api_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  url TEXT NOT NULL,
  method TEXT NOT NULL,
  request TEXT DEFAULT NULL,
  response TEXT DEFAULT NULL,
  status INTEGER NOT NULL DEFAULT 0,
  response_time_ms INTEGER DEFAULT 0,
  is_enabled INTEGER NOT NULL DEFAULT 1,
  checked_at DATETIME DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id TEXT DEFAULT NULL UNIQUE,
  name TEXT NOT NULL,
  share_link TEXT NOT NULL UNIQUE,
  cloud_name TEXT NOT NULL,
  type TEXT DEFAULT NULL,
  remarks TEXT DEFAULT NULL,
  account_id INTEGER DEFAULT NULL,
  is_replaced INTEGER DEFAULT 0,
  health_status TEXT DEFAULT 'unknown',
  health_message TEXT DEFAULT NULL,
  checked_at DATETIME DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_resources_name ON resources(name);
CREATE INDEX IF NOT EXISTS idx_resources_health ON resources(health_status);

CREATE TABLE IF NOT EXISTS cloud_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cloud_name TEXT NOT NULL,
  account_name TEXT NOT NULL,
  credential TEXT NOT NULL,
  extra_data TEXT DEFAULT NULL,
  username TEXT DEFAULT NULL,
  vip_status INTEGER DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  is_valid INTEGER NOT NULL DEFAULT 1,
  invalid_reason TEXT DEFAULT NULL,
  total_space_bytes INTEGER DEFAULT 0,
  used_space_bytes INTEGER DEFAULT 0,
  left_space_bytes INTEGER DEFAULT 0,
  priority INTEGER NOT NULL DEFAULT 0,
  weight INTEGER NOT NULL DEFAULT 10,
  transferred_count INTEGER DEFAULT 0,
  last_used_at DATETIME DEFAULT NULL,
  last_keepalive_at DATETIME DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_accounts_lookup ON cloud_accounts(cloud_name, is_active, is_valid);
CREATE INDEX IF NOT EXISTS idx_accounts_priority ON cloud_accounts(cloud_name, priority ASC, updated_at ASC);

CREATE TABLE IF NOT EXISTS system_config (
  config_key TEXT PRIMARY KEY,
  config_value TEXT DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS temp_share (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  original_url TEXT NOT NULL,
  title TEXT DEFAULT NULL,
  cloud_name TEXT NOT NULL,
  temp_share_url TEXT NOT NULL,
  file_id TEXT NOT NULL,
  account_id INTEGER DEFAULT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  expires_at DATETIME NOT NULL,
  last_accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  deleted_at DATETIME DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_temp_share_lookup ON temp_share(cloud_name, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_temp_share_original ON temp_share(original_url);

CREATE TABLE IF NOT EXISTS telegram_channel (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel TEXT NOT NULL UNIQUE,
  title TEXT DEFAULT NULL,
  is_enabled INTEGER NOT NULL DEFAULT 1,
  health_status TEXT DEFAULT 'unknown',
  latency_ms INTEGER DEFAULT 0,
  result_count INTEGER DEFAULT 0,
  health_message TEXT DEFAULT NULL,
  checked_at DATETIME DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telegram_channel_name ON telegram_channel(channel);

CREATE TABLE IF NOT EXISTS system_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  log_type TEXT NOT NULL,
  action TEXT NOT NULL,
  query_text TEXT DEFAULT NULL,
  status_code INTEGER NOT NULL DEFAULT 200,
  error_message TEXT DEFAULT NULL,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  result_count INTEGER DEFAULT 0,
  client_ip TEXT DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_created_at ON system_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_type_created ON system_logs(log_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_status_created ON system_logs(status_code, created_at DESC);
