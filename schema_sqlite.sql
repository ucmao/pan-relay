-- SQLite 表结构与初始化数据

-- ----------------------------
-- Table structure for `api_config`
-- ----------------------------
CREATE TABLE IF NOT EXISTS api_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  url TEXT NOT NULL,
  method TEXT NOT NULL,
  request TEXT DEFAULT NULL,
  response TEXT DEFAULT NULL,
  status TEXT NOT NULL DEFAULT 'unknown',
  response_time_ms INTEGER DEFAULT 0,
  checked_at DATETIME DEFAULT NULL,
  is_enabled INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------
-- Table structure for `telegram_channel`
-- ----------------------------
CREATE TABLE IF NOT EXISTS telegram_channel (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel TEXT NOT NULL UNIQUE,
  title TEXT DEFAULT NULL,
  is_enabled INTEGER NOT NULL DEFAULT 1,
  health_status TEXT NOT NULL DEFAULT 'unknown',
  latency_ms INTEGER NOT NULL DEFAULT 0,
  result_count INTEGER NOT NULL DEFAULT 0,
  health_message TEXT DEFAULT NULL,
  checked_at DATETIME DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telegram_channel_enabled ON telegram_channel(is_enabled);

-- ----------------------------
-- Table structure for `resources`
-- ----------------------------
CREATE TABLE IF NOT EXISTS resources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id TEXT DEFAULT NULL UNIQUE,
  name TEXT NOT NULL,
  share_link TEXT NOT NULL UNIQUE,
  cloud_name TEXT NOT NULL,
  type TEXT DEFAULT NULL,
  remarks TEXT DEFAULT NULL,
  is_replaced INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_resources_name ON resources(name);

-- ----------------------------
-- Table structure for `cookie_config`
-- ----------------------------
CREATE TABLE IF NOT EXISTS cookie_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cloud_name TEXT NOT NULL UNIQUE,
  cookie TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------
-- Table structure for `system_config`
-- ----------------------------
CREATE TABLE IF NOT EXISTS system_config (
  config_key TEXT PRIMARY KEY,
  config_value TEXT DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------
-- Table structure for `temp_share`
-- ----------------------------
CREATE TABLE IF NOT EXISTS temp_share (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  original_url TEXT NOT NULL,
  title TEXT DEFAULT NULL,
  cloud_name TEXT NOT NULL,
  temp_share_url TEXT NOT NULL,
  file_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  expires_at DATETIME NOT NULL,
  last_accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  deleted_at DATETIME DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_temp_share_lookup ON temp_share(cloud_name, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_temp_share_original ON temp_share(original_url);

