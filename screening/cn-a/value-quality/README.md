# 全 A 股价值质量筛选层

这里维护独立于单公司研究系统的当前价值质量池。

## 文件

- `pool.json`：唯一结果源，保存当前全量池。
- `current.md`：由 `pool.json` 确定性生成的人类可读投影，禁止手改。
- 筛选方法：`prompts/screening/cn-a-value-quality.md`。

本目录不保存每次筛选的日期化快照。成员增删、分层变化和备注调整直接替换当前池；需要历史时查看 Git。

## 隔离边界

本层不会写入研究状态、研究队列、自选池、公司报告或研究日志。池内成员也不会自动成为 `candidate` 或 `covered`。单公司研究层同样不会根据本池改变任何状态。

池内不保存现价、估值、收益率、仓位、交易建议、研究状态、任务 ID 或报告路径。临时行情、财务抓取和机械评分可以用于筛选，但只留在临时目录。

## 命令

```bash
python -m trading_os quality-pool status
python -m trading_os quality-pool validate
python -m trading_os quality-pool list
python -m trading_os quality-pool list --tier core_moat
python -m trading_os quality-pool replace --input <完整池.json>
```

`replace` 只接受完整快照，并同时重建 `current.md`。不要直接编辑生成文件。
