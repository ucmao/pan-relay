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
  status INTEGER NOT NULL DEFAULT 0,
  response_time_ms INTEGER DEFAULT 0,
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

-- ----------------------------
-- Default data for `api_config`
-- ----------------------------
INSERT OR IGNORE INTO api_config (name, url, method, request, response, status, response_time_ms, is_enabled) VALUES
('qkpanso', 'https://qkpanso.com/v1/search/disk', 'post', '{"page": 1, "q": "[[keyword]]", "user": "", "exact": false, "format": [], "share_time": "", "size": 15, "type": "", "exclude_user": [], "adv_params": {"wechat_pwd": "", "platform": "pc"}}', 'data.list[*].[disk_name, link]', 0, 7605, 0),
('uuxiao', 'https://uuxiao.cn/api/user/search?name=[[keyword]]', 'get', '', 'data[*].[name, url]', 1, 390, 1),
('hhlqilongzhu', 'https://www.hhlqilongzhu.cn/api/ziyuan_nanfeng.php?keysearch=[[keyword]]', 'get', '', 'data[*].[title, data_url]', 1, 996, 1),
('ptger', 'https://files.ptger.cn/api/files/vagueQuery?name=[[keyword]]', 'get', '', 'data[*].source.[name, url]', 1, 388, 1),
('6789o', 'https://zy.6789o.com/duanjuapi/search.php?text=[[keyword]]', 'get', '', 'data[*].[name, viewlink]', 1, 2039, 1),
('ahfi', 'https://api.ahfi.cn/api/short?text=[[keyword]]', 'get', '', 'data[*].[name, viewlink]', 0, 2375, 0),
('lbbb', 'https://dj.lbbb.cc/api.php?limit=20&text=[[keyword]]', 'get', '', 'datas.data[*].[name, link]', 0, 40387, 0),
('110t', 'https://ys.110t.cn/api/ajax.php?act=search&name=[[keyword]]', 'get', '', 'data[*].[name, url]', 0, 46, 0),
('ycubbs', 'https://ai-img.ycubbs.cn/api/duanju/search?name=[[keyword]]', 'get', '', 'data[*].[name, url]', 1, 383, 1),
('qsdurl', 'https://api.qsdurl.cn/tool/duanju?name=[[keyword]]', 'get', '', '[*].[name, url]', 0, 23344, 0),
('mywl', 'https://cx.mywl.top/api/duanju/search?keyword=[[keyword]]', 'get', '', 'data[*].[title, url]', 0, 10452, 0),
('kuleu', 'https://api.kuleu.com/api/action?text=[[keyword]]', 'get', '', 'data[*].[name, viewlink]', 1, 1232, 1),
('kuoapp', 'https://kuoapp.com/duanju/api.php?param=1&name=[[keyword]]', 'get', '', 'data[*].[name, url]', 1, 1956, 1),
('狗狗盘搜', 'https://gogopanso.com:3642/search?keyword=[[keyword]]', 'get', '', 'data[*].[name, downurl]', 1, 1148, 1),
('趣盘搜', 'https://v.funletu.com/search', 'post', '{"style": "get", "datasrc": "search", "query": {"id": "", "datetime": "", "courseid": 1, "categoryid": "", "filetypeid": "", "filetype": "", "reportid": "", "validid": "", "searchtext": "[[keyword]]", "fileid": ""}, "page": {"pageSize": 10, "pageIndex": 1}, "order": {"prop": "sort", "order": "desc"}, "message": "请求资源列表数据"}', 'data[*].[title, url]', 0, 866, 0),
('pansou', 'https://so.252035.xyz/api/search?kw=[[keyword]]', 'get', '', 'data.merged_by_type.* | [].[note, url]', 1, 5753, 1);

-- ----------------------------
-- Default data for `resources`
-- ----------------------------
INSERT OR IGNORE INTO resources (file_id, name, share_link, cloud_name, type, remarks) VALUES
('file_123456', '电影资源分享', 'https://pan.baidu.com/s/test0001', '百度网盘', '电影', '这是一个电影资源分享'),
('file_789012', '音乐专辑合集', 'https://www.aliyundrive.com/s/test0001', '阿里云盘', '音乐', '精选音乐专辑合集'),
('file_345678', '软件工具包', 'https://pan.quark.cn/s/test0001', '夸克网盘', '软件', '常用软件工具包'),
('file_901234', '学习资料', 'https://cloud.189.cn/t/test0001', '天翼云盘', '文档', '学习资料合集'),
('file_567890', '图片素材', 'https://pan.xunlei.com/s/test0001', '迅雷网盘', '图片', '高清图片素材集');
