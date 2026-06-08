/**
 * 防御性内容过滤器
 * 识别并移除模型可能输出的违规内容（XML 标签、上下文块、重复问题等）
 *
 * 防御策略：
 * 1. 完整 XML 标签（含闭合）：捕获并移除整块
 * 2. 未闭合 XML 标签：单独移除遗留的开标签/闭标签
 * 3. HTML 实体编码变体：`&lt;tag&gt;` 形式
 * 4. 上下文块标记：行首和行中均匹配
 * 5. 重复问题开场白：中文常见模式
 * 6. 内部标识符泄漏：tenantId、family_id 等
 *
 * 先规范化输入（移除零宽字符）再执行匹配，避免 Unicode 绕过。
 */

const ZERO_WIDTH_CHARS = /[​-‍﻿]/g

// 禁止输出的模式列表
const FORBIDDEN_PATTERNS = [
  // XML 标签及其内容（捕获整个标签块）
  /<system_instructions\b[^>]*>[\s\S]*?<\/system_instructions>/gi,
  /<user_question\b[^>]*>[\s\S]*?<\/user_question>/gi,
  /<system[_-]?instructions\b[^>]*>[\s\S]*?<\/system[_-]?instructions>/gi,
  /<user[_-]?question\b[^>]*>[\s\S]*?<\/user[_-]?question>/gi,

  // 未闭合的 XML 标签（单独的开/闭标签残留）
  /<\/?(system[_-]?instructions|user[_-]?question)\b[^>]*>/gi,

  // HTML 实体编码的标签
  /&lt;\/?(system[_-]?instructions|user[_-]?question)[^&]*&gt;/gi,

  // 上下文块标记（不区分行首/行中，大小写不敏感）
  /(?:^|\s)User Context:[^\n]*/gi,
  /(?:^|\s)System Prompt:[^\n]*/gi,
  /(?:^|\s)Internal Context:[^\n]*/gi,
  // Context: 必须在行首（避免误伤 "in this context: ..." 类正常文本）
  /^Context:.*$/gim,

  // 重复用户问题模式（中文常见开场白，行首匹配）
  /^你问的是[：:].*$/gm,
  /^问题是[：:].*$/gm,
  /^您的问题是[：:].*$/gm,
  /^关于您问的[：:].*$/gm,

  // 内部标识符泄漏（行首或前导空白，大小写不敏感）
  /^(?:\s*)tenantId\s*[:=].*$/gim,
  /^(?:\s*)family_id\s*[:=].*$/gim,
  /^(?:\s*)user_id\s*[:=].*$/gim,
  /^(?:\s*)internal_user_id\s*[:=].*$/gim,
]

/**
 * 过滤 AI 回答内容
 * @param raw 原始回答文本
 * @returns 过滤后的干净文本
 */
export function filterAIContent(raw: string): string {
  if (!raw) return ''

  // 1. 规范化：移除零宽字符（防止 Unicode 绕过）
  let filtered = raw.replace(ZERO_WIDTH_CHARS, '')

  // 2. 依次应用所有禁止模式
  for (const pattern of FORBIDDEN_PATTERNS) {
    filtered = filtered.replace(pattern, '')
  }

  // 3. 清理多余空行（过滤后可能留下连续空行）
  filtered = filtered.replace(/\n{3,}/g, '\n\n')

  // 4. 清理开头和结尾的空白
  return filtered.trim()
}
