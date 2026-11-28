# Trading OS 可视化研究台

这是研究资产的只读展示，不维护第二套公司估值或研究状态，也不因价格变动创建任务。所有完整报告统一按财报周期保存在 `reports/`。

**线上地址：** [trading-os-dashboard.csz99126.workers.dev](https://trading-os-dashboard.csz99126.workers.dev)

## 公司池

研究台内「公司池」视图聚合 **A 股与港股（港股通口径）** 两个活跃市场的双轨商业质量判断（`compounder` 复利质量 + `inflection_growth` 产业拐点）；旧 `/screening` 链接保留跳转。市场、轨道、领域、行业、层级及关键词筛选支持跨公司比较；详情面板提供筛选轨道、标准行业主题、关键研究问题、经营指标、年度记录及来源。移动端使用独立详情弹层。筛选条件与公司引用保存在链接中，可导出当前列表。

数据从 `screening/{cn-a|hk}/value-quality/pool.json` 生成（退役美股单股资产已移至 `archive/retired-us-single-stocks/`，研究台「筛选方法与范围」提供 25 家全球产业龙头参照表入口）。v2 保留原有判断字段，v3 增加发行人关联、指标和完整取舍理由，两者均支持可选 `track` 与 `industry_topic`。全部市场按发行人合并 A/H 多地上市，单一市场展示对应证券。

活跃公司市场为 `CN` 与 `HK`；宏观与宽基参照中保留 `US`（对应国内可投纳指100 / 标普500 QDII ETF 与跨市场基准）。缺少正式研报时展示真实空状态，A 股与 H 股分别按本地财报与交易币种/税负核算，不直接混同估值。

## 默认展示

研究视图置于页面顶部，切换时保持导航位置。跟踪进度以行内摘要呈现；研究标准和模型口径通过「研究口径」弹层查看。移动端保留搜索与市场选择，其他条件收在「筛选」中；表格固定公司列，公司名称可直接打开研报。

**最新周期模型**默认使用动态重点跟踪池，只显示状态依据报告中按现行兼容标准完成的结果。报告按财报周期和资料截止理解，不声明在今天仍然有效；最新周期没有兼容标准结果时不回退旧模型。

**跟踪进度**列动态重点跟踪池公司，区分尚无周期报告、待按现行标准研究、状态需修复和研究完成。**全市场**提供跨范围的元数据查询，不混入历史标准模型。

**研报库**按公司直接打开最新财报周期，并可切换其他周期。同周期只保留最后一次完整研究；历史周期不加载现价，不附当前摘要，不以旧模型计算今天的IRR。未知标准如实显示“历史标准未确认”。

标准声明、兼容性与后续研究命令见[现行研究展示标准](../research/standards/README.md)。协调器验收后由 `research complete` 把采用的标准直接写入研究状态，不另建登记文件。标准缺失或格式错误时停止构建，不回退到原全市场估值表。

## 数据、慢快分离与行情

`npm run data`（`prebuild` / `predev` 会自动触发）从研究状态、质量池、标准声明、发布目录（含 `industryState`/`macroState`）、A/H 港股通税桥、国内美股 QDII 目录与全球龙头参照确定性生成 `public/data/`：

- 当前目录在生成时移除不合格旧估值及旧 `decisionProfile`/`scenarios`；当前表、行情请求、排序、汇总及导出使用共同的结果筛选规则。
- 同步生成供下游决策 AI 调用的 **`decision-index.json`** 与全球对标 **`global-benchmarks.json`**；同时可下载 `current-research.json/.csv`（核心池现行结果）、`all-current-research.json/.csv`（全部现行结果）以及不含估值的 `research-progress.json`。导出绝不保存实时行情、动态 IRR 或赔率结果。
- 顶部折叠**宏观与宽基环境条**集中展示跨市场周期因子、四大指数基准及国内 6 只美股 QDII ETF 名录；**最新周期模型**按实时价格即时计算 5 年基准 IRR、**港股通税后 IRR（仅扣分红 20%/28% 税率，终端价值 0% 资本利得税）**、**四情景不对称度（上行空间 / 周期底下行空间 / 赔率比）**，并支持按决策视角（核心防御 / 产业拐点 / 港股通与A-H）、轨道、行业周期与宏观顺逆风筛选。

腾讯行情为主，东方财富为备援，两者不可用时显示空白。行情时间、财报周期、研究资料截止和完成入库时间分开显示。所有即时回报、赔率及筛选视角均为研究辅助，不构成收益承诺或自动交易指令。

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

必须从仓库根目录开始构建，因为数据生成步骤会读取外层的`coverage/`、`research/`和`screening/`。`dashboard/public/data/`与`dashboard/dist/`都是构建产物，不提交到Git。

需要手动复核部署包或补发时仍可使用：

```bash
npx wrangler login
npm run deploy:dry-run
npm run deploy
```

仍使用构建输出`dist/server/wrangler.json`部署到Cloudflare Workers，生产Worker名称为`trading-os-dashboard`。没有授权登录时，不以其他账号或连接绕过；本地/CI构建与实际上线分别报告。

## 跨市场与港股通本地预览

股票研究状态从 `coverage/{cn-a|hk}` 读取；报告存放在 `research/companies/{CN|HK}/{ticker}/reports`。A 股阅读链接兼容原六位代码，港股使用 `HK-00700` 等带市场路径（退役美股单股资产已移出活跃管线）。

腾讯与东方财富报价支持 A 股和港股实时行情，币种与响应实时核对；不可用或币种不匹配时保留空值。港股通分红税后 IRR 仅针对 `market === "HK"` 按 `capitalReturnProfile.southbound_dividend_tax_rate` 或 `ahBridge.southboundDividendTaxRate` 动态估算。

开发预览使用 `npm run dev -- --host 127.0.0.1 --port 4183`。已有预览服务时，浏览器隔离检查可用 `TRADING_OS_TEST_URL=http://127.0.0.1:4183 node tests/standard-browser.mjs`，检查不会关闭外部预览进程。

## 行业与宏观发布

`research/publications.json` 显式登记行业、宏观报告和参考文章。构建前检查路径、日期、市场、资料截止及版本重复；正文和发布目录统一导出。未登记的旧行业框架、提示词及内部文档不会进入阅读列表。

中国行业导航由 `research/industries/catalog.json` 定义。目录只保存有顺序的大类、主题及经济范围，主题ID与发布条目的 `topic` 一致；报告日期、版本和摘要仍由发布目录提供。构建将目录确定性投影至既有 `documents.json` 的 `industryCatalog`，页面按实际目录生成导航，不固定大类和主题数量。尚无报告的主题保留名称、范围及简洁空状态。

行业发布条目显式设置 `regionId: "cn"` 后进入“中国行业”；该范围按经营地域确定，页面不以上市市场筛选。缺省地区标识的旧报告进入“历史与海外”，保留原版本与资料截止。`region=cn|archive`、`group`、`topic`、`version`可恢复阅读位置；原有明确旧版本的深链自动进入对应档案。当前运行指标只在中国区最新已发布报告显式连接时展示，档案不继承独立更新的指标。

主题默认展示最近版本，读者可按发布日期切换并通过链接恢复原版本。长文提供按需目录；移动端使用紧凑主题选择，表格可独立横向浏览。已撤回版本显示原因，不自动用旧报告替代。指标方法明确分类，不计作已完成的时点研究。无已发布报告时展示空状态，已登记的指标参考文章仍可独立阅读。

公司、行业和宏观正文可用仓库相对路径互相引用。阅读器只转换发布目录中登记的行业/宏观正文，以及构建目录中实际存在的公司财报周期；链接保留明确版本和章节。`documents.json` 中的公司报告路径索引由既有报告目录生成，只用于校验阅读链接。未登记文件、内部框架和不安全地址显示为普通文字；模型下载继续遵循既有文件范围。

章节锚点由解析后的标题文本生成：字母小写，保留中文、数字、下划线与连字符，去除其他标点，空白转为连字符；重复标题依次追加 `-1`、`-2`。例如 `## 需求与回款` 可引用为 `文件.md#需求与回款`。目录与正文共用同一锚点；代码块中的标题不进入目录。已有公司标题锚点和行业 `section-行号` 链接保留别名。跨页章节会在异步正文加载后定位，历史行业版本不显示当前指标，公司旧周期不加载行情。

顶层取消长期精选，旧 `/selection` 地址转到公司池。公司研报和现行模型展示规则保持独立。
