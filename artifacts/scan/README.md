# Scan Artifacts

`artifacts/scan/` 保存正式扫描快照和同名人工解读。

命名：

- 原始扫描快照：`{system}-YYYYMMDD.json`
- 人工解读：`{system}-YYYYMMDD.md`

`YYYYMMDD` 使用扫描快照对应的 effective date。人工解读必须与 JSON 同名，只改变扩展名。

临时诊断、实验扫描和大体积中间产物放到 `artifacts/scan/tmp/`，不要入库。
