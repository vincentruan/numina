---
capability: time_machine
name: 财务时光机
description: 模拟 What-if 消费场景和财务推演，给出分析建议
category: simulation
icon: clock
color: "#a855f7"
route: /ai/time-machine
input_mode: free_text
placeholder: 描述你想模拟的财务场景
examples:
  - 如果我每月多还1000元贷款会怎样？
  - 买一辆20万的车对家庭财务影响多大？
allowed_roles: [member, admin]
thinking: true
mcp_tools: []
subagent_enabled: true
plan_mode: true
max_tokens: 2000
---
