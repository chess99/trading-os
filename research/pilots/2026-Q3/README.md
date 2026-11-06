# 2026-Q3 研究入口

本期 A 股研究包含191家公司，完整报告按公司保存，结构化结果由 `coverage/cn-a/research_state.jsonl` 绑定。该数量是本期已完成范围；下一周期排期继续读取当时的动态重点池。

185家公司提供数值价值与五年持有人模型。五粮液、泰格医药、九典制药、宁沪高速、伟明环保、中微公司保留有原因的空值，具体商业、资本或权益边界见各公司报告。空值不按零价值处理，也不回退旧模型。

## 阅读与复算

公司文件位于：

```text
research/companies/CN/{ticker}/reports/2026-Q3.md
research/companies/CN/{ticker}/models/2026-Q3.py
research/companies/CN/{ticker}/models/2026-Q3-output.json
```

可读计算模块与必要输入在同一公司目录；多文件模型可以使用 `models/2026-Q3/`。请使用当前仓库源码树运行，部分历史适配器还使用 `research/model_io.py`。附件不再承诺仅下载一个脚本即可完成复算。

例如：

```bash
python research/companies/CN/300693/models/2026-Q3.py
python research/companies/CN/300693/models/2026-Q3-check.py
```

`*-output.json` 保存采用的简明结果；详细路径通过对应程序的可选入口重新生成到工作目录。文件边界见[研究文件规范](../../../docs/research-artifacts.md)。

## 检查入口

```bash
python -m trading_os validate
python scripts/check-research-artifacts.py
python research/pilots/2026-Q3/verify-models.py
python research/pilots/2026-Q3/verify-models.py --recompute --symbol CN:300693
```

最后一条实际运行源码，并将新结果与采用结果对照。省略 `--symbol` 可检查本期全部公司；无完整数值模型的公司单独记为不可数值复算，不计入成功数。默认合同检查不运行金融计算。

当前源码、必要输入及声明的 Python 运行环境足以完成常规复算，无需旧 Git 对象、下载档案或保存的全量轨迹。模型执行验证计算链与数据一致性，商业假设和未来现金实现仍按报告中的证据与条件判断。

## 本期修订

本次完成阳光电源、泰格医药、盛弘股份的后续完整研究，并独立重建华明装备、科达利、星宇股份。六份报告资料截止为2026年11月6日；其余报告按各自声明的截止阅读。

范围、数学保持及工程验证见[收尾说明](../../../docs/reviews/2026-11-q3-cleanup.md)。
