# 全 A 股价值质量筛选层

这里维护独立于单公司研究系统的当前价值质量池。

## 文件

- `pool.json`：唯一结果源，保存当前全量池。
- `current.md`：由 `pool.json` 确定性生成的人类可读投影，禁止手改。
- 筛选方法：`prompts/screening/cn-a-value-quality.md`。

本目录不保存每次筛选的日期化快照。成员增删、分层变化和备注调整直接替换当前池；需要历史时查看 Git。

## 隔离边界

本层不会写入研究状态、研究队列、自选池、公司报告或研究日志。池内成员也不会自动成为 `candidate` 或 `covered`。单公司研究层同样不会根据本池改变任何状态。

池内不保存现价、估值、证券回报率、仓位、交易建议、研究状态、任务 ID 或报告路径。财务抓取与去价格化的机械整理只留在临时目录；证券价格不得进入质量排序、门槛或分层。

## 命令

```bash
python -m trading_os quality-pool status
python -m trading_os quality-pool validate
python -m trading_os quality-pool list
python -m trading_os quality-pool list --tier core_moat
python -m trading_os quality-pool replace --input <完整池.json>
python -m trading_os quality-pool rebuild
```

`replace` 只接受完整快照，并同时重建 `current.md`。不要直接编辑生成文件。

当前采用 v2：每家公司四项必填判断及 1—3 个公开来源，独立在市证券清单与实际复核范围嵌入 JSON。身份数量不代表财务复核完成。

JSON 替换是唯一提交点；投影失败会明确返回名单已保存及警告。`status/list` 可继续读取源，`rebuild` 只重建投影，`validate` 严格检查一致性，但不认证商业论据。
