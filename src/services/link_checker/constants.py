# src/services/link_checker/constants.py

# --- 状态常量 ---
STATE_OK = "ok"                      # 链接正常有效，且包含有效资源文件
STATE_BAD = "bad"                    # 链接失效、过期、违规、已删除、或文件列表为空
STATE_LOCKED = "locked"              # 链接需要提取码/访问码且未提供或错误
STATE_UNCERTAIN = "uncertain"        # 网络波动、触发风控验证码、状态无法断定
STATE_UNSUPPORTED = "unsupported"    # 暂不支持免登录检测的平台

# --- 缓存 TTL（秒） ---
CACHE_TTL_OK = 1800      # 有效链接缓存 30 分钟 (避免频繁请求网盘风控)
CACHE_TTL_BAD = 600      # 失效链接缓存 10 分钟
CACHE_TTL_OTHER = 300    # 其他状态（如需密码/未知）缓存 5 分钟
