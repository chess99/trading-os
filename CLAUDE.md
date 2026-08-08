# Claude Guide

先读根目录 `AGENTS.md`，它是本仓库唯一的 Agent 说明。

本仓库使用一套轻量流程：主 Agent 批量初筛，只有 `research_now` 才派单公司 Agent；一家公司由一个 Agent 端到端完成，不做多角色复核或阶段审批。全市场状态、自选池、当前报告和每日收盘价格扫描的详细约定见 `playbooks/simple-research.md`。
