# Trading OS 可视化研究台

这是研究资产的只读展示，不维护第二套公司估值或研究状态，也不因价格变动创建任务。所有完整报告统一按财报周期保存在 `reports/`。

## 默认展示

**最新周期模型**默认使用动态重点跟踪池，只显示状态依据报告中按现行兼容标准完成的结果。报告按财报周期和资料截止理解，不声明在今天仍然有效；最新周期没有兼容标准结果时不回退旧模型。

**跟踪进度**列动态重点跟踪池公司，区分尚无周期报告、待按现行标准研究、状态需修复和研究完成。**全市场**提供跨范围的元数据查询，不混入历史标准模型。

**研报库**按公司直接打开最新财报周期，并可切换其他周期。同周期只保留最后一次完整研究；历史周期不加载现价，不附当前摘要，不以旧模型计算今天的IRR。未知标准如实显示“历史标准未确认”。

标准声明、兼容性与后续研究命令见[现行研究展示标准](../research/standards/README.md)。协调器验收后由 `research complete` 把采用的标准直接写入研究状态，不另建登记文件。标准缺失或格式错误时停止构建，不回退到原全市场估值表。

## 数据与行情

`npm run data`从研究状态、质量池、标准声明与周期报告生成 `public/data/`。当前目录在生成时就移除不合格旧估值及摘要；当前表、行情请求、排序、汇总及导出使用共同的结果筛选规则。

可下载 `current-research.json/.csv`（核心池现行结果）、`all-current-research.json/.csv`（全部现行结果）以及不含估值的 `research-progress.json`。导出不保存实时行情或动态IRR；历史原文可查但不混入当前导出。

腾讯行情为主，东方财富为备援，两者不可用时显示空白。只对最新兼容标准周期按其冻结的五年模型计算机械IRR；已有现金路径问题继续暂停，独立三年终值仍保留模型接口。行情时间、财报周期、研究资料截止和完成入库时间分开显示。机械回报及相对价值位置不是收益承诺、买入信号或投资授权，默认不按回报高低排名。

## 运行与验证

```bash
node dashboard/scripts/report-standards.mjs validate  # 在仓库根目录
cd dashboard
npm ci
npm run dev
# 或
npm test
npx tsc --noEmit
npm run lint
```

`research-display-checks.yml`自动测试展示隔离、标准兼容性、null估值、否定结论、范围及历史阅读，并运行浏览器检查。正常测试不修改研究状态、队列、质量池或正式报告。

## 部署

网页是构建时只读快照。Cloudflare Workers Builds连接GitHub仓库，`main`每次推送后直接重新生成资料投影并部署，不等待GitHub Actions检查完成。

Cloudflare项目使用下列设置：

- 生产分支：`main`
- 根目录：仓库根目录
- 构建命令：`cd dashboard && npm ci --no-audit --no-fund && npm run build`
- 部署命令：`cd dashboard && npx wrangler deploy --config dist/server/wrangler.json`
- Node.js：`22.13.0`或更高版本

必须从仓库根目录开始构建，因为数据生成步骤会读取外层的`coverage/`、`research/`、`screening/`和`selection/`。`dashboard/public/data/`与`dashboard/dist/`都是构建产物，不提交到Git。

需要手动复核部署包或补发时仍可使用：

```bash
npx wrangler login
npm run deploy:dry-run
npm run deploy
```

仍使用构建输出`dist/server/wrangler.json`部署到Cloudflare Workers，生产Worker名称为`trading-os-dashboard`。没有授权登录时，不以其他账号或连接绕过；本地/CI构建与实际上线分别报告。
