# 数值复算与资料说明

信息截止保持2026-10-27。金额除每股外为亿元。报告和candidate范围均3.6—5.9元，未来五期分配0.16/0.18/0.20/0.22/0.24元，Y5普通股价值4.37—7.53元。

`python 2026-Q3.py` 使用Python标准库，默认写脚本同目录2026-Q3-output.json；输出含12种完整情景逐年表、项目贡献、母公司与合并现金/权益、独立尾期和摘要。复制单个脚本到新目录、从另一个cwd运行，输出逐字节相同。

`python independent-check.py` 使用字面输入另行实现低端、基准及每度电降价1分情景，以二维Newton法求融资，而生产函数使用固定点迭代；不读取生产结果余额或年表作为独立计算输入。最终与实际生产函数逐项比对价值、Y5终值以及Y1/Y5/Y20债务与母公司债务，价值差小于1e-9。独立现金误差最大约8.92e-10亿元。

生产函数另有真实手算特例：账面100、利润8、分配8、权益成本8%、零增长，当前和Y5价值均100；利润10而分配8、成本10%的留存情形，与20年8元现金流加100元终值的手算相等。所有情景每年断言合并现金、母公司现金和资本守恒。20/30/40年数值收敛测试基准值均4.6512647243441165元；年数不代表法律上的分配或内部贷款归还承诺。

剩余收益法和分配DCF在同一清洁盈余桥下数学相等，不是两套独立经营证据。折旧更新、未来营运资本、少数权益、债务及经营资本留存均进入尾期。经济上划预算不冒充逐主体已审计可分配余额。


## 原始公开来源

- https://disc.static.szse.cn/disc/disk03/finalpage/2026-08-26/f5bd7adc-d03c-49ab-b370-cd6ddc6c8f04.PDF
- https://www.mee.gov.cn/xxgk2018/xxgk/xxgk09/202608/t20260813_1163971.html
- https://static.cninfo.com.cn/finalpage/2026-10-28/1225630598.PDF
- https://static.cninfo.com.cn/finalpage/2026-10-10/1225598378.PDF
- https://static.cninfo.com.cn/finalpage/2026-08-29/1225531682.PDF
- https://static.cninfo.com.cn/finalpage/2026-10-16/1225606815.PDF
- https://pdf.dfcfw.com/pdf/H2_AN202604291821751208_1.pdf
- https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2023-04-28/138547_20230428_1F6D.pdf
- https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-06-24/244158_20260624_4V2B.pdf
