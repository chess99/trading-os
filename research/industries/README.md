# 中国行业研究与内部参考

中国行业的分类与经济范围由[行业目录](catalog.json)维护，大类用于导航，主题对应完整研究。完整报告保存于 `<主题>/reports/YYYY-MM-DD.md`，通过[发布目录](../publications.json)登记后进入网页。研究要求见[行业研究规范](../../prompts/industry-research.md)。

中国研究按国内需求、供给、价格、利润及资本机制展开。中国经营的相关竞争者均属于产业证据范围；海外需求、原料和贸易规则作为实际外部驱动。海外地区的完整行业判断单独研究。网页分别提供中国行业与历史及海外档案，报告日期和范围随各版本保留。

下列既有内容保存研究过程中反复遇到、可供多家公司使用的产业问题，作为内部参考保留。专题帮助理解竞争机制和寻找资料，不提供公司当前估值、投资资格或交易判断；公司状态与当前报告仍以全市场状态和正式报告指针为准。

## 使用与维护

- 产业框架按经营问题组织，专题用于复用跨公司的研究方法。框架覆盖不等于已对全部细分做跨周期实证；每篇披露实际样本和资料缺口。
- 每篇注明复核日期、材料截止、适用范围及实际阅读深度，区分公开事实、公司自述、推断和未决问题。引用给出公开 URL、资料日期和页码/章节。
- 保存解释机制所需的证据和反例，不重复搬运完整财报、公司估值或动态行情。单家公司或单个产品的现象不能直接升级为整个行业结论。
- 使用前核验决定性资料的时效及公司适用性；专题不是共识认证，也不能成为新估值的先验。正式公司报告必须独立写清必要事实、推理和来源。
- 新材料只有改变机制、适用边界或未决问题时才更新专题。只维护当前文本，历史通过 Git 回看，不复制公司公告扫描、研究队列或自动调度。
- 多家公司并行时，由协调器在本轮验收后归并可复用发现；不要让多个 worker 同时覆盖同一专题。每次只提交自己修改的内容。
- 专题和方法审查不能代替正式公司更新。发现足以改变公司正式结论的事实，仍按原公司研究流程处理，不在这里写新的 current。

## 跨市场使用

资料复用按实际经营范围、时点和机制核对。中国与海外研究可以引用相同方法和全球产业事实，各自形成地区现状与结论。财年、币种、证券单位与跨境现金差异见[跨市场产业比较](cross-market-guide.md)。行业名称映射只提供导航。

## 既有内部行业框架

下列入口保留既有公司研究参考与行业名称路由。`python -m trading_os industry validate` 检查路由与重复，正式行业成果按上方目录及发布登记查阅。

| 主行业 | 主行业 | 主行业 |
|---|---|---|
| [银行](sectors/banks.md) | [非银金融](sectors/nonbank-financials.md) | [房地产](sectors/real-estate.md) |
| [食品饮料](sectors/food-beverage.md) | [家用电器](sectors/household-appliances.md) | [商贸零售](sectors/retail.md) |
| [农林牧渔](sectors/agriculture.md) | [医药生物](sectors/pharmaceuticals.md) | [美容护理](sectors/beauty.md) |
| [轻工制造](sectors/light-manufacturing.md) | [纺织服饰](sectors/textiles-apparel.md) | [社会服务](sectors/social-services.md) |
| [传媒](sectors/media.md) | [综合](sectors/comprehensive.md) | [煤炭](sectors/coal.md) |
| [石油石化](sectors/oil-gas.md) | [基础化工](sectors/chemicals.md) | [钢铁](sectors/steel.md) |
| [有色金属](sectors/nonferrous.md) | [建筑材料](sectors/construction-materials.md) | [建筑装饰](sectors/construction.md) |
| [公用事业](sectors/utilities.md) | [环保](sectors/environmental.md) | [交通运输](sectors/transportation.md) |
| [电子](sectors/electronics.md) | [通信](sectors/communications.md) | [计算机](sectors/computers.md) |
| [机械设备](sectors/machinery.md) | [电力设备](sectors/electrical-equipment.md) | [汽车](sectors/automotive.md) |
| [国防军工](sectors/defense.md) | | |

每篇说明细分机制、决定性问题、反证、领先变量、现金及资本、估值方法、真实样本比较与后续取证。业务跨行业时同时参考相关专题，主行业仅作导航，不把整个集团硬套单一模型。

## 运行指标

主题可维护 `indicators.json`，保存经过核验的低频关键序列及正式月报入口。指标按发布节奏更新，完整研报保留自己的资料截止。最新报告通过发布条目的 `indicatorSourcePath` 连接当前指标；历史报告不自动获得新数据。更新规范见[行业运行指标更新](../../prompts/industry-indicators.md)。

## 问题专题

- [汽车照明：升级、议价与股东收益](automotive-lighting.md)：以星宇披露为主要样本，补充一家同业能力陈述；用于检验产品升级的利润归属，不替代全球车灯竞争研究。

- [动力电池公司的经营机制核验](../../prompts/company/sector-guides/power-batteries.md)：用于公司研究拆解电芯、系统、客户自研与二供、技术替代和每Wh经济性；不提供公司当前结论。
