# 研究成果与发布

`companies/`保存公司财报周期研究；`industries/`保存行业成果及既有内部框架；`macro/`保存宏观与市场研究。网页只展示明确发布的内容。

## 正式报告

公司报告继续使用公司状态与既有验收流程。行业与宏观报告使用稳定主题和发布日期：

```text
research/industries/<topic>/reports/YYYY-MM-DD.md
research/macro/<topic>/reports/YYYY-MM-DD.md
research/macro/reference/<topic>.md
research/publications.json
```

主题粒度由实际经济问题决定。行业报告必须覆盖历史、供需现状、竞争、利润归属、前景及反证；宏观报告必须把环境变化传到行业或现金流假设。报告面向独立读者，执行规范放在`prompts/`与`playbooks/`。

季度复核不强制生成报告。结论或关键证据实质改变时新发完整版本，主题入口自动选择最近版本；最近版本被撤回时显示原因，读者可主动选择旧版本。格式修复可在同一版本完成。影响结论的错误须交代更正，旧版本可标为`withdrawn`，正文保留用于理解历史。

## 发布目录

`publications.json`的`schemaVersion`为1，`documents`是显式登记列表。每项字段：

- `id`：唯一小写字母、数字与连字符标识。
- `kind`：`industry`或`macro`；`type`：`report`或`reference`。
- `topic`：稳定主题标识。一个主题只属于一种内容类型。
- `publishedOn`：发布日期，`YYYY-MM-DD`。
- `revision`：同日修订编号，默认1；报告文件名为日期，编号大于1时追加`-r2`等后缀。参考文章只使用编号1，持续修订原文。
- `informationCutoff`：报告资料截止，不晚于发布日期；参考文章为`null`。
- `markets`：实际适用的上市市场`CN/HK/US`；`regions`：实际经营或宏观覆盖地域的文字数组。两者分别说明。
- `summary`：简洁判断或参考文章用途；`sourcePath`：仓库内正文路径。
- `status`：`published`或`withdrawn`；撤回时必须有`withdrawalReason`，并在阅读界面提示。

登记表示人工确认可公开阅读，校验通过只说明结构完整。参考文章不能充当当期研究。未登记正文、旧行业框架、提示词、执行计划与日报均不自动发布。测试使用的历史版本只存在临时夹具中。

正式报告可引用同目录内可分发的小型证据文件，并说明单位、来源与信息版本；当前网页只导出登记的Markdown正文，证据附件在仓库中阅读。引入网页附件展示前须另行实现文件校验与导出。

## 参考材料和日常观察

旧`industries/sectors/`、`automotive-lighting.md`与`cross-market-guide.md`保留作公司研究参考，相关链接及行业名称路由继续有效；它们尚未按新的完整行业报告要求发布。

指标解释与方法文章只维护一份当前正文，通过Git查看修订。日报、新闻扫描和取证过程保存在仓库外；只有改变中长期判断的证据才在正式报告中归纳。数据缓存不进入版本库。
