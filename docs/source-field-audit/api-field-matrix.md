# API 字段矩阵

字段覆盖数量为本轮适配结果计数；`—` 表示当前探测未产生统计结果。响应键来自原始字段路径探测。

| API 预设 | 状态 | 条数 | 密码 | 时间 | 简介 | 封面 | 扩展字段/响应观察 |
|---|---|---:|---:|---:|---:|---:|---|
| 悠悠小站 API | 有结果 | 2 | 0 | 2 | 0 | 0 | all、day、id |
| 龙珠南风资源 API | 有结果 | 20 | 3 | 0 | 0 | 0 | title、url；提取码可从链接识别；证书过期 |
| PTGer资源 API | 有结果 | 253 | 253 | 253 | 0 | 0 | id |
| 6789短剧 API | 有结果 | 5 | 0 | 5 | 0 | 0 | addtime、data[]、name、viewlink |
| 翼彩短剧 API | 有结果 | 101 | 0 | 0 | 0 | 0 | 空数组/未返回 JSON |
| 酷乐短剧 API | 有结果 | 5 | 0 | 5 | 0 | 0 | addtime、data[]、name、viewlink |
| KuoApp短剧 API | 有结果 | 2 | 0 | 2 | 0 | 2 | episodes、id、label、state |
| 狗狗盘搜 API | 有结果 | 9 | 0 | 9 | 0 | 0 | downtype、mid、shareid、type |
| 252035盘搜 API | 失败/无结果 | 0 | — | — | — | — | 早期 HTTP 200：note、url、password、datetime、source、images；本轮 403/超时 |
| 量子影视资源 API | 有结果 | 20 | 0 | 20 | 20 | 20 | detail、group_id、group_key、type_id、type_id_1、type_name、user_counter_ver、user_fav、user_like、vod_actor、vod_area、vod_author、vod_behind、vod_class、vod_color |
| 极客盘 API | 有结果 | 15 | 1 | 15 | 0 | 0 | categoryid、checked、courseid、filetypeid、id、recommend、size、sort、state、top、updatetime、uploaderid、valid、views、viewshistory |
