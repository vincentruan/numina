/**
 * System agent IDs — snowflake IDs for built-in system agents.
 *
 * These IDs are seeded by backend bootstrap/agents.py and must stay in sync.
 * System agents have family_id=0 and cannot be modified or disabled.
 */

// Numina: brand-primary system agent, holds all family-enabled skills
export const NUMINA_AGENT_ID = '100000000000005'

// Asset Report: dedicated system agent for family asset health reports
// Scoped to skills=["report"], specialized persona for comprehensive analysis
export const ASSET_REPORT_AGENT_ID = '100000000000006'

/**
 * Agent names for lookup by agent_name field.
 */
export const NUMINA_AGENT_NAME = 'numina'
export const ASSET_REPORT_AGENT_NAME = 'asset-report'