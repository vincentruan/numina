/**
 * 防御性内容过滤器
 * 识别并移除模型可能输出的违规内容（XML 标签、上下文块、重复问题等）
 */

// 禁止输出的模式列表
const FORBIDDEN_PATTERNS: RegExp[] = [
  // XML 标签及其内容（捕获整个标签块）
  /<system_instructions>[\s\S]*?<\/system_instructions>/gi,
  /<user_question>[\s\S]*?<\/user_question>/gi,

  // 上下文块标记（行首）
  /^User Context:.*$/gm,
  /^System Prompt:.*$/gm,
  /^Context:.*$/gm,
  /^Internal Context:.*$/gm,

  // 重复用户问题模式（中文常见开场白）
  /^你问的是[：:].*$/gm,
  /^问题是[：:].*$/gm,
  /^您的问题是[：:].*$/gm,
  /^关于您问的[：:].*$/gm,

  // 内部标识符泄漏
  /^tenantId:.*$/gm,
  /^family_id:.*$/gm,
  /^user_id:.*$/gm,
  /^internal_user_id:.*$/gm,
]

/**
 * 过滤 AI 回答内容
 * @param raw 原始回答文本
 * @returns 过滤后的干净文本
 */
export function filterAIContent(raw: string): string {
  let filtered = raw

  for (const pattern of FORBIDDEN_PATTERNS) {
    filtered = filtered.replace(pattern, '')
  }

  // 清理多余空行（过滤后可能留下连续空行）
  filtered = filtered.replace(/\n{3,}/g, '\n\n')

  // 清理开头和结尾的空白
  return filtered.trim()
}