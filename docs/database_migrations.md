# 数据库迁移开发约定

pan-relay 使用 SQLite，并用 `PRAGMA user_version` 记录数据库结构版本。服务每次启动时会：

1. 版本落后时，先在数据库旁边生成一致性快照 `pan_relay.db.bak-v<旧版本>-<时间>`，最多保留 5 份；
2. 执行 `schema_sqlite.sql`（新库建表；老库已存在的表不受影响）；
3. 按顺序执行 `src/db/migrations.py` 中尚未执行的迁移，每个迁移独立事务，成功后写入版本号。

任一迁移失败会回滚该迁移并阻止服务启动，日志中会给出备份文件位置。数据库不会停留在"半升级"状态。

---

## 什么时候需要写迁移

只要改动会让**已部署用户的数据库**和新代码对不上，就必须写迁移：

| 改动 | 只改 schema_sqlite.sql 够吗？ | 需要迁移？ |
| :--- | :---: | :---: |
| 新增一张表 | ✓（`CREATE TABLE IF NOT EXISTS`） | 不需要 |
| 已有表新增列 | ✗ 老库不会自动加列 | **需要** |
| 已有表新增索引 | 索引依赖新列时会让老库启动报错 | **需要** |
| 改列名 / 改类型 / 删列 / 改约束 | ✗ | **需要**（重建表） |
| 用新表替换旧表 | ✗ 旧数据会"消失" | **需要**（搬数据） |
| 修改默认配置数据 | — | 视情况 |

> 反面教材：账号池版本用 `cloud_accounts` 替换了 `cookie_config`，但没有迁移数据，老用户升级后凭据全部丢失。v2 迁移就是为补这个坑。

---

## 如何新增一个迁移

1. 同时修改 `schema_sqlite.sql`，让**全新安装**直接得到最终结构。
2. 在 `src/db/migrations.py` 中写迁移函数，并追加到 `MIGRATIONS` 末尾：

```python
def add_resources_view_count(conn: sqlite3.Connection) -> None:
    """v3：resources 新增浏览次数"""
    if "view_count" not in _columns(conn, "resources"):
        conn.execute("ALTER TABLE resources ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0;")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_resources_views ON resources(view_count);")


MIGRATIONS = [
    (1, "基线：补齐历史字段与求片工单表", ensure_legacy_columns),
    (2, "旧版 cookie_config 凭据导入账号池", migrate_cookie_config_to_accounts),
    (3, "resources 新增浏览次数", add_resources_view_count),
]
```

3. 在 `tests/test_db_migrations.py` 中补用例：至少覆盖"老库升级后数据还在"和"重复启动不出错"。

### 规则

* **版本号严格递增，已发布的迁移不要修改或删除。** 写错了就再加一个新迁移去修正。
* **迁移函数必须幂等。** 新安装的库里 schema 已经建好了表和列，迁移会在这样的库上再跑一遍，所以先判断再执行（`_columns`、`_table_exists`、`IF NOT EXISTS`）。
* **不要在迁移里 `commit()`、`BEGIN` 或调用 `executescript()`。** 事务由 `run_migrations` 统一管理，`executescript` 会隐式提交，破坏回滚。
* **不要在迁移里依赖业务代码**（`src.db.accounts`、service 等）。业务代码会随版本变化，迁移只用原生 SQL，保证将来任何版本都能从头升级。
* **默认保留旧表和旧数据**，确认没有问题后，再在后续版本中单独清理。

### 改列 / 删列：重建表

SQLite 的 `ALTER TABLE` 能力有限，改类型、删列、改约束需要重建：

```python
def rebuild_temp_share(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE temp_share_new (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          original_url TEXT NOT NULL,
          -- ……新的完整结构……
        );
    """)
    conn.execute("""
        INSERT INTO temp_share_new (id, original_url /* , ... */)
        SELECT id, original_url /* , ... */ FROM temp_share;
    """)
    conn.execute("DROP TABLE temp_share;")
    conn.execute("ALTER TABLE temp_share_new RENAME TO temp_share;")
    # 重建表后，原表上的索引需要重新创建
    conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_share_xxx ON temp_share(xxx);")
```

---

## 本地验证

```bash
python -m unittest tests.test_db_migrations -v
```

用真实数据验证时，先把生产库复制到本地再启动，不要直接拿正在运行的库做实验：

```bash
sqlite3 /opt/pan-relay/data/pan_relay.db ".backup '/tmp/pan_relay_test.db'"
SQLITE_DB_PATH=/tmp/pan_relay_test.db python app.py
sqlite3 /tmp/pan_relay_test.db "PRAGMA user_version;"
```
