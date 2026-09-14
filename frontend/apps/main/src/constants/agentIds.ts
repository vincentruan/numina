/**
 * System agent IDs — snowflake IDs for built-in system agents.
 *
 * These IDs are seeded by backend bootstrap/agents.py and must stay in sync.
 * System agents have family_id=0 and cannot be modified or disabled.
 */

// Numina: brand-primary system agent, holds all family-enabled skills
export const NUMINA_AGENT_ID = '100000000000005'

// Asset Report: dedicated system agent for family asset health reports
export const ASSET_REPORT_AGENT_ID = '100000000000006'

// Import Parse: dedicated system agent for financial document parsing
export const IMPORT_PARSE_AGENT_ID = '100000000000007'

// Finance Coach: dedicated system agent for financial coaching advice
export const FINANCE_COACH_AGENT_ID = '100000000000008'

// Wish Advice: dedicated system agent for wish savings advice
export const WISH_ADVICE_AGENT_ID = '100000000000009'

// Dashboard Narrative: dedicated system agent for monthly financial narratives
export const DASHBOARD_NARRATIVE_AGENT_ID = '100000000000010'

/**
 * Agent names for lookup by agent_name field.
 */
export const NUMINA_AGENT_NAME = 'numina'
export const ASSET_REPORT_AGENT_NAME = 'asset-report'
export const IMPORT_PARSE_AGENT_NAME = 'import-parse'
export const FINANCE_COACH_AGENT_NAME = 'finance-coach'
export const WISH_ADVICE_AGENT_NAME = 'wish-advice'
export const DASHBOARD_NARRATIVE_AGENT_NAME = 'dashboard-narrative'
