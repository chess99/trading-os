# Trading OS Agent Guide

除非用户主动要求切分支，否则直接在当前分支开发。文档默认使用中文。完成一个完整迭代后，只提交本次修改的文件；提交前检查暂存区，禁止带入用户或其他 Agent 的无关修改。

## 唯一事实源

- 分市场状态：`coverage/{cn-a|hk|us}/research_state.jsonl`。
- 分市场研究队列：`coverage/{cn-a|hk|us}/research_queue.jsonl`。
- 公司报告：`research/companies/{CN|HK|US}/{ticker}/reports/YYYY-{FY|Q1|H1|Q3}.md`。一个财报周期只保留一份完整研究；同周期重研覆盖该文件，下一周期才新增文件。`basis_report_path` 精确绑定结构化研究状态所依据的报告，`report_period` 保存对应周期；它们不是网页展示范围。
- 港美股第一层精选池：`screening/hk/value-quality/pool.json`、`screening/us/value-quality/pool.json`；规范见 `prompts/screening/international-value-quality.md`。使用 `quality-pool --market hk|us` 维护，与同市场正式研究及周期排期关联。
- 独立价值质量池：`screening/cn-a/value-quality/pool.json`；筛选规范见 `prompts/screening/cn-a-value-quality.md`，可读投影 `current.md` 只能由池文件确定性生成。

公司报告进入 Git。worker 返回的结构化 JSON 和 `report_markdown` 在验收前只是候选稿；验收失败直接丢弃，不写报告。同周期重研以完整新正文覆盖原周期文件，并同步结构化状态；Git 保存修改历史，但网页不提供同周期旧修订入口。不同周期报告并存，不使用 `stale`、事件日志或新闻触发表达报告状态。

仓库不保存证券价格触发线、armed/hit/rearm 状态或每日收盘扫描结果。正式研究可以冻结不含现价的 `return_model` 持有人回报模型输入；IRR 只允许由展示层使用实时价格现场机械求解，不得写回研究状态或解释为买入信号、收益率门槛或投资授权。

旧 manager-screen、quick/targeted/scoped/deep 阶段预算、价格触发、claim/seal、calibration、独立承保、challenger、仲裁和组合审批均已退役，不得重新引入。

## 研究判断与表达

单公司研究与验收须完整阅读 [统一深研提示词](prompts/company/standard-deep-research.md) 和其 [核验附录](prompts/company/research-verification.md)。价值概念的唯一解释源是主提示词的 [价值定义](prompts/company/standard-deep-research.md#价值定义)；其他文件只引用，不建立第二套估值含义。

先形成长期商业判断，再用财务、资本和权益模型检验。允许有依据的未来预测进入核心路径，并说明关键判断如何改变模型；未来未兑现本身不是排除理由。正文结论先行、围绕决定性问题展开，不固定 16 章；保留程序所需标题与结构化合同。核验充分不等于正文堆满核验过程，语言明确也不等于事实或预测确定。

派发遵循[单公司任务简报](prompts/company/research-task-brief.md)：每家公司使用不继承协调对话的新上下文；研究者只完成本公司及必要返工。正式报告面向独立投资读者，用户对话、执行过程、模型身份和验收说明留在工作记录。写作优先直接陈述判断，避免用无必要的“不是……而是……”引入读者并未持有的观点。

公司是否值得长期拥有、价格相对价值是否有吸引力、是否发现可靠错价，是三个不同判断。没有非共识发现不妨碍形成“好公司、价格合理”的结论；主张超额回报优势时必须解释具体分歧。商业和定价评价不升级为仓位、买入线或自动交易授权。

## 独立价值质量筛选层

价值质量筛选按市场只维护 `screening/{cn-a|hk|us}/value-quality/pool.json`，不得在筛选事务中修改研究状态、队列或公司报告。财报季排期命令读取当时的动态池成员创建周期任务；成员退出后不删除历史报告，成员进入后可从最新财报周期开始研究。

筛选可以独立获取公开信息，也可以把正式报告当作普通参考，但公司研究状态不是入池条件。池中不得保存现价、估值、回报率、仓位、交易动作、任务 ID、报告路径或 `return_model`。结果只维护当前全量版本，历史通过 Git 查看；`current.md` 禁止手改。池成员和 A/B 分层允许随每轮筛选增删调整，任何代码或展示不得把某次池规模写成固定名单。

处理价值质量池时必须完整阅读 `prompts/screening/cn-a-value-quality.md`；港美股另读 `prompts/screening/international-value-quality.md`，使用独立的 `quality-pool status / validate / list / replace / rebuild` 命令。v2/v3 每家公司必须有竞争优势、普通股现金、反证、分层理由及公开来源；证券身份清单与实际复核范围嵌入池文件。JSON 是唯一提交点，投影失败用 rebuild 恢复，不能把机械校验当作商业认证。

## 角色与结果

- 财报季使用 `research enqueue-period --period <周期>`，只为当时的动态重点跟踪池创建缺失槽位；不同公司可并行，同一公司只允许一个任务。
- 人工认为报告质量不足时，使用 `research enqueue-rewrite` 显式重写已存在的同周期槽位。规范升级默认等待下一财报周期，确需立即处理也走人工重写。
- 所有任务统一使用 `prompts/company/standard-deep-research.md` 及其核验附录；没有研究强度等级、固定分钟数、复核 Agent 或经理审批。
- 公司研究状态只使用 `unseen / ignore / covered`；证券范围只使用 `active / inactive`；任务只使用 `queued / running`，触发类型只使用 `periodic / manual_rewrite`。
- 正式结果只有 `ignore / covered`，两种结果都必须完成商业、财务、治理、估值和风险研究，并追加完整、自足的正式报告。
- `covered / ignore` 是最近完成周期的研究结论，不表达报告在今天是否“有效”。报告永远按其财报周期和资料截止阅读，后续新闻留待下一周期吸收。

正式报告必须脱离历史版本独立可读。不得用“参见前序报告”“历史分析继续有效”“沿时间线回看”等句子代替正文。任何正常化利润、`value_range`、`return_model` 输入、核心逻辑、风险排序或 `covered / ignore` 结论变化，都必须重写所属财报周期的完整正式报告。

每次新正式研究都必须提交非空 `return_model_note`；能够可靠建模时同时提交结构化 `return_model`，否则提交 `return_model: null`，并在 note 中说明原因。V1 统一使用五年主口径：五个年度的普通股每股现金分配和第五年末普通股每股终值区间；三年口径可选，但必须单独研究第三年末终值，不得从五年终值机械折算。当前价值与未来终值的边界按主提示词“价值定义”执行，不相互代用。行业和公司可以采用不同的经营预测与终值方法，最终都必须归一到这一接口。

单公司层不输出仓位、`buy_now`、随现价变化的 IRR、承保意见或组合动作，也不输出收益率阈值、概率权重、价格触发状态或交易建议。事实数字应能从公开来源复核；预测假设须标明依据、范围和模型后果，不要求未来数值已被公开文件承诺。不建立 evidence ledger、SHA 权限链或多角色复核链。

## 周期节奏

- 正式研究只由财报周期或用户显式人工重写触发，不因政策、新闻、价格或单项公告在周期中途创建报告。
- 周期只使用 `YYYY-FY / YYYY-Q1 / YYYY-H1 / YYYY-Q3`；是否对某一层成员执行四个周期，由当轮排期决定。
- 下一周期报告完整吸收自上次截止后的重要经营、治理、资本和行业事实。没有 update、stale、公告扫描检查点或事件去重状态。
- 同周期人工重写仍须提交完整自足正文并重新验收，不能用补丁段落替代研究。

## 写入纪律

- worker 不直接修改共享 JSONL；协调器校验并原子写入。
- 同一公司最多一个活动任务。
- 新正式研究必须显式提交 `report_period`。同周期通过验收后覆盖该周期报告；跨周期才新增文件。`basis_report_path` 与 `report_period` 必须同步指向最新完成周期，未通过验收的候选稿直接丢弃。
- 修改共享状态后执行 `python -m trading_os validate`。

## 开始工作

系统分层：动态重点跟踪池见 `prompts/screening/cn-a-value-quality.md`；产业框架见 `research/industries/README.md`；单公司研究与验收沿用下列工作流；长期精选见 `selection/principles.md` 和 `prompts/selection/long-term-selection.md`。

先读：

1. `playbooks/simple-research.md`
2. `prompts/goals/cn-all-a-continuous-research.md`

单公司研究及其验收另须完整阅读主提示词与核验附录；价值质量池任务另读 `prompts/screening/cn-a-value-quality.md`。

常用命令见 `README.md`。

## 现行标准与历史展示

执行新研究的协调验收或修改网页前，再读 [现行研究展示标准](research/standards/README.md)。`research/standards/registry.json` 发布现行标准及显式兼容版本；协调器实质验收后调用 `research complete`，由它把当时的标准 ID、规范版本和完成时间与最新周期状态一次写入，不另建报告级登记、哈希或撤销文件。

网页默认动态重点跟踪池并展示最新周期中按现行兼容标准完成的模型；暂无法估值及研究后ignore不自动排除。全市场仍可按财报周期阅读已有报告，非最新周期不加载现价或其他版本摘要。范围、结论、标准兼容和资料时点分别处理。

网页与导出改动运行 `node dashboard/scripts/report-standards.mjs validate`，并执行dashboard测试、类型检查及浏览器隔离测试；原研究状态校验仍须通过。该脚本只做 registry 与状态一致性校验，不提供第二次验收流程。

## 产品与文档表达

界面围绕研究者的浏览、比较、检索和阅读任务设计。优先呈现判断、关键问题及必要证据；执行计划、对话约定、模型身份和交付汇报留在对话，不写入产品内容。资料时点和重要口径限制以靠近相关信息的简洁说明呈现。

面向读者的文档直接解释用途、事实与判断。避免无必要的“不是……而是……”及预设读者错误观点的反驳句。工程文档保留真实需要的接口、维护与验证说明，不用任务复述填充正文。

## 跨市场研究

港股和美股使用同一完整研究标准，并阅读 `prompts/company/cross-market.md`。研究台包含公司池、跟踪进度、最新周期模型与全部档案，顶层保留研究台、研报库、产业研究和长期精选。

研究命令通过 `research --market cn-a|hk|us` 选择状态分区；全局 `--market` 适用于状态与校验。港美股排期须有实际已披露的财务依据。`enqueue-latest` 默认预览，显式 `--apply` 才写队列。A/H等同发行人的并行任务互斥。

外国公司报告槽位使用发行人财年；`financial_basis`同时保存实际期末、披露日和来源。正式结果另需`security_basis`，明确交易币种、普通股/ADS/类别及换算单位。最新财报由已披露的实际期末决定；港股未披露季度结果时使用最新半年或全年资料，不制造季度槽位。跨期保留旧报告并在新报告检验旧假设。
