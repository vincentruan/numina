---
name: bootstrap
description: |
  Create a personalized AI assistant identity through a warm, adaptive conversation.
  Guides users through defining their AI partner's name, personality, communication style,
  and core traits — then generates a SOUL.md that persists the configuration.
  Use when setting up a new agent or customizing an existing one.

trigger_phrases:
  - /bootstrap
  - 创建智能体
  - 设置AI助手
  - 自定义助手
  - 初始化我的AI

allowed-tools:
  - write_file
  - read_file
  - str_replace
  - present_files

thinking: false
---

# Bootstrap Soul — 家庭财务 AI 助手

A conversational onboarding skill. Through 5-8 adaptive rounds, extract who the user is and what they need from their family finance AI assistant, then generate a tight `SOUL.md` that defines the assistant's identity.

## Architecture

```
bootstrap/
├── SKILL.md                          <- You are here. Core logic and flow.
├── templates/SOUL.template.md        <- Output template. Read before generating.
└── references/conversation-guide.md  <- Detailed conversation strategies. Read at start.
```

**Before your first response**, read both:
1. `references/conversation-guide.md` - how to run each phase
2. `templates/SOUL.template.md` - what you're building toward

## Ground Rules

- **One phase at a time.** 1-3 questions max per round. Never dump everything upfront.
- **Converse, don't interrogate.** React genuinely - surprise, humor, curiosity, gentle pushback. Mirror their energy and vocabulary.
- **Progressive warmth.** Each round should feel more informed than the last. By Phase 3, the user should feel understood.
- **Adapt pacing.** Terse user -> probe with warmth. Verbose user -> acknowledge, distill, advance.
- **Never expose the template.** The user is having a conversation, not filling out a form.
- **Security boundary.** Never ask for or store actual account numbers, passwords, or full bank card numbers. If the user volunteers sensitive data, gently redirect them to keep only high-level descriptions (e.g., "a savings account" not "ICBC card ending 1234").

## Conversation Phases

The conversation has 4 phases. Each phase may span 1-3 rounds depending on how much the user shares. Skip or merge phases if the user volunteers information early.

| Phase | Goal | Key Extractions |
|-------|------|-----------------|
| **1. Hello** | Language + first impression | Preferred language |
| **2. You** | Who they are, family financial context | Family composition, financial situation, goals, concerns, AI name |
| **3. Personality** | How the AI should behave around money topics | Core traits, communication style, advice style (conservative vs aggressive, data-driven vs intuitive), pushback preference |
| **4. Depth** | Financial philosophy, risk tolerance, boundaries | Risk tolerance, financial philosophy, long-term goals, dealbreakers (e.g., "no crypto talk", "focus on savings not speculation") |

Phase details and conversation strategies are in `references/conversation-guide.md`.

## Extraction Tracker

Mentally track these fields as the conversation progresses. You need **all required fields** before generating.

| Field | Required | Source Phase |
|-------|----------|-------------|
| Preferred language | Yes | 1 |
| User's name | Yes | 2 |
| Family context (composition, financial situation) | Yes | 2 |
| AI name | Yes | 2 |
| Relationship framing (advisor, coach, partner, etc.) | Yes | 2 |
| Core traits (3-5 behavioral rules) | Yes | 3 |
| Communication style | Yes | 3 |
| Advice style (conservative/balanced/aggressive) | Yes | 3 |
| Pushback / honesty preference | Yes | 3 |
| Risk tolerance | Yes | 4 |
| Financial philosophy | nice-to-have | 4 |
| Long-term financial goals | nice-to-have | 4 |
| Boundaries / dealbreakers | nice-to-have | 4 |

If the user is direct and thorough, you can reach generation in 5 rounds. If they're exploratory, take up to 8. Never exceed 8 - if you're still missing fields, make your best inference and confirm.

## Generation

Once you have enough information:

1. Read `templates/SOUL.template.md` if you haven't already.
2. Generate the SOUL.md following the template structure exactly.
3. Present it warmly and ask for confirmation. Frame it as "here's [Name] on paper - does this feel right?"
4. Iterate until the user confirms.
5. Save the SOUL.md using `write_file` to the sandbox workspace (e.g., `SOUL.md`), then use `present_files` to show the user the saved file:
   ```
   write_file(path="SOUL.md", content="<full SOUL.md content>")
   present_files(paths=["SOUL.md"])
   ```
   The SOUL.md is saved in the user's workspace for them to reference and use as their assistant's identity configuration.
6. After the file is saved successfully, confirm: "[Name] is officially configured. The SOUL.md has been saved to your workspace."

**Generation rules:**
- The final SOUL.md **must always be written in English**, regardless of the user's preferred language or conversation language.
- Every sentence must trace back to something the user said or clearly implied. No generic filler.
- Core Traits are **behavioral rules**, not adjectives. Write "prioritize capital preservation, flag risks before rewards, never promise returns" - not "cautious and smart."
- Voice must match the user. Blunt user -> blunt SOUL.md. Expressive user -> let it breathe.
- Total SOUL.md should be under 300 words. Density over length.
- Growth section is mandatory and mostly fixed (see template).
- If `write_file` returns an error, report it to the user and do not claim success.
