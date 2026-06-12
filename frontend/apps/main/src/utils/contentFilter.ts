/**
 * 防御性内容过滤器
 * 识别并移除模型可能输出的违规内容（XML 标签、上下文块、重复问题等）
 *
 * 防御策略（采用 deerflow 的 INTERNAL_MARKER_TAGS 模式）：
 * 1. DeerFlow 内部标记标签：uploaded_files, system-reminder, memory, current_date
 * 2. 完整 XML 标签（含闭合）：捕获并移除整块
 * 3. 未闭合 XML 标签：单独移除遗留的开标签/闭标签
 * 4. HTML 实体编码变体：`&lt;tag&gt;` 形式
 * 5. 上下文块标记：行首和行中均匹配
 * 6. 重复问题开场白：中文常见模式
 * 7. 内部标识符泄漏：tenantId、family_id 等
 * 8. 工具调用内部标识：调用工具、MCP 内部消息等
 *
 * 先规范化输入（移除零宽字符）再执行匹配，避免 Unicode 绕过。
 *
 * 错误边界：所有异常被捕获并返回原始输入，确保流式渲染不被中断。
 * 性能监控：执行时间超过阈值时记录告警（dev 环境）。
 */

// Zero-width characters: U+200B (ZWSP), U+200C-U+200D (ZWNJ/ZWJ), U+FEFF (ZWNBSP)
// Using Unicode escape sequences to avoid ESLint irregular-whitespace error
const ZERO_WIDTH_CHARS = /[\u200B-\u200D\uFEFF]/gu

// 性能告警阈值（毫秒）- 200ms 为合理的慢调用阈值
const PERFORMANCE_WARN_THRESHOLD_MS = 200

// DeerFlow 内部标记标签（直接采用 deerflow 的 INTERNAL_MARKER_TAGS 模式）
// 参考：deer-flow-reference/frontend/src/core/messages/utils.ts
const INTERNAL_MARKER_TAGS = [
  'uploaded_files',
  'system-reminder',
  'memory',
  'current_date',
  'context',
  'user_context',
] as const

// 构建内部标记标签的正则表达式（匹配完整标签块）
const INTERNAL_MARKER_RE = new RegExp(
  `<(${INTERNAL_MARKER_TAGS.join('|')})\\b[^>]*>[\\s\\S]*?<\\/\\1>`,
  'gi',
)

// 未闭合的内部标记标签（单独的开/闭标签残留）
const UNCLOSED_MARKER_RE = new RegExp(
  `<\\/?(?:${INTERNAL_MARKER_TAGS.join('|')})\\b[^>]*>`,
  'gi',
)

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

  // 问答复述模式：AI 先复述用户问题，再回答
  // 使用 TRANSFORM_PATTERNS 处理（需要保留回答部分）

  // 联网搜索、思考过程等提示词
  /^联网搜索[：:].*$/gm,
  /^正在搜索[：:].*$/gm,
  /^搜索结果[：:].*$/gm,
  /^思考过程[：:].*$/gm,
  /^分析过程[：:].*$/gm,
  /^推理步骤[：:].*$/gm,

  // DeerFlow/Agent 内部标识
  /^DeerFlow.*$/gm,
  /^Agent.*执行.*$/gm,
  /^智能体.*执行.*$/gm,

  // Prompt/System 内容泄漏模式
  /^Prompt[：:].*$/gm,
  /^System[：:].*$/gm,
  /^提示词[：:].*$/gm,
  /^系统提示[：:].*$/gm,
  /^用户输入[：:].*$/gm,
  /^当前对话[：:].*$/gm,

  // 工具调用内部标识
  /^调用工具[：:].*$/gm,
  /^正在调用[：:].*$/gm,
  /^工具返回[：:].*$/gm,

  // MCP 内部信息
  /^MCP.*$/gm,
  /^正在获取.*$/gm,
  /^获取家庭.*$/gm,
  /^查询家庭.*$/gm,

  // DeerFlow Memory 系统内容泄漏
  // 格式 1：完整 <system-reminder><memory> XML 块（最常见）
  /<system-reminder\b[^>]*>[\s\S]*?<\/system-reminder>/gi,

  // 格式 2：未闭合的 memory 相关标签残留
  /<\/?memory\b[^>]*>/gi,
  /<\/?current_date\b[^>]*>/gi,

  // 格式 3：DeerFlow Memory 节标题（支持 dash 前缀格式）
  // "- Personal:" 或 "Personal:" 都匹配
  /^[-\s]*Personal[：:][\s\S]*?(?=^[-\s]*Current Focus|^[-\s]*Recent|^History|^Facts|<\/memory|$)/gim,
  /^[-\s]*Current Focus[：:][\s\S]*?(?=^[-\s]*Recent|^History|^Facts|<\/memory|$)/gim,
  /^[-\s]*Recent[：:][\s\S]*?(?=^History|^Facts|<\/memory|$)/gim,
  /^History[：:][\s\S]*?(?=^Facts|<\/memory|$)/gim,
  /^Facts[：:][\s\S]*?(?=<\/memory|^[^\[]|$)/gim,

  // 格式 4：User Context 整块（包含所有子节）
  /^User Context[：:][\s\S]*?(?=^History|^Facts|<\/memory|$)/gim,

  // DeerFlow Memory 事实条目格式（支持空格变体）
  /^[-\s]*\[context\s*\|[^\]]*\][^\n]*$/gm,
  /^[-\s]*\[goal\s*\|[^\]]*\][^\n]*$/gm,
  /^[-\s]*\[correction\s*\|[^\]]*\][^\n]*$/gm,
  /^[-\s]*\[preference\s*\|[^\]]*\][^\n]*$/gm,
  /^[-\s]*\[insight\s*\|[^\]]*\][^\n]*$/gm,

  // 联网搜索启用提示（整块过滤）
  /联网搜索\n\n用户已启用联网搜索[\s\S]*?你可以调用搜索工具获取[^\n]*\n/gm,
  /联网搜索\n\n用户已启用联网搜索[\s\S]*?\n\n/gm,

  // 日期标记行（内部时间戳，宽松匹配）
  /20\d{2}-\d{2}-\d{2},\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)/gi,

  // 内部标识符泄漏（行首或前导空白，大小写不敏感）
  /^(?:\s*)tenantId\s*[:=].*$/gim,
  /^(?:\s*)family_id\s*[:=].*$/gim,
  /^(?:\s*)user_id\s*[:=].*$/gim,
  /^(?:\s*)internal_user_id\s*[:=].*$/gim,
]

/**
 * 转换模式列表：需要保留部分内容的模式（使用捕获组）
 * 每个元素包含 pattern 和 replacement，用于 .replace(pattern, replacement)
 */
const TRANSFORM_PATTERNS = [
  // 问答复述模式 1：问题？根据...，答案 → 移除问题和整个 preamble（无换行）
  // 例如："问题？根据最新的家庭财务数据，您家的净资产为" → "您家的净资产为"
  { pattern: /^([^？]*？)根据[^，]*，[\s]*/gm, replacement: '' },

  // 问答复述模式 2：问题？[换行]根据...，答案 → 移除问题和整个 preamble（有换行）
  // 例如："问题？\n根据最新的家庭财务数据，您家的净资产为" → "您家的净资产为"
  // 注意：此模式必须在模式3之前，避免模式3先移除问题行导致此模式失效
  { pattern: /^([^？]*？)[\s\n]+根据[^，]*，[\s]*/gm, replacement: '' },

  // 问答复述模式 3：问题？直接接答案开头（无换行，无 preamble）
  // 包括：您家、截至...等开头 → 移除问题保留答案开头
  // 例如："问题？您家的净资产为" → "您家的净资产为"
  // 例如："问题？截至2024年底" → "截至2024年底"
  { pattern: /^([^？]*？)(您家|截至)/gm, replacement: '$2' },

  // 问答复述模式 4：独立的问题行（后跟换行）→ 移除
  // 匹配：以？结尾的短行（<50字符，排除长 rhetorical questions）+ 换行 + 任意下一行
  // 例如："问题？\n答案" → "答案"
  // 注意：(?=. 确保下一行存在才移除，避免误删最后一个问题行
  // 注意：长度限制 50 字符避免误删 AI 的 rhetorical questions（如 "为什么会这样？")
  // 注意：此模式在模式2之后，因为模式2专门处理根据 preamble
  { pattern: /^([^？]{0,45}？)[\s\n]+(?=.)/gm, replacement: '' },
]

/**
 * 内部核心过滤逻辑（无错误边界）
 * 仅用于测试和性能基准
 * @internal
 */
export function filterAIContentCore(raw: string): string {
  if (!raw) return ''

  // 1. 规范化：移除零宽字符（防止 Unicode 绕过）
  let filtered = raw.replace(ZERO_WIDTH_CHARS, '')

  // 2. 采用 deerflow 的 stripInternalMarkers 模式（移除内部标记标签）
  // 参考：deer-flow-reference/frontend/src/core/messages/utils.ts
  filtered = filtered.replace(INTERNAL_MARKER_RE, '')
  filtered = filtered.replace(UNCLOSED_MARKER_RE, '')

  // 3. 依次应用所有禁止模式（替换为空字符串）
  for (const pattern of FORBIDDEN_PATTERNS) {
    filtered = filtered.replace(pattern, '')
  }

  // 4. 应用转换模式（保留部分内容的捕获组替换）
  for (const { pattern, replacement } of TRANSFORM_PATTERNS) {
    filtered = filtered.replace(pattern, replacement)
  }

  // 5. 清理多余空行（过滤后可能留下连续空行）
  filtered = filtered.replace(/\n{3,}/g, '\n\n')

  // 6. 清理开头和结尾的空白
  return filtered.trim()
}

/**
 * 过滤 AI 回答内容（带错误边界和性能监控）
 * @param raw 原始回答文本
 * @param userQuestion 可选的用户问题文本，用于移除开头的逐字复述
 * @returns 过滤后的干净文本；异常时返回原始输入
 */
export function filterAIContent(raw: string, userQuestion?: string): string {
  if (!raw) return ''

  const startTime = performance.now()

  try {
    let result = filterAIContentCore(raw)

    // Remove question echo: if assistant content starts with the user's question verbatim
    if (userQuestion && result) {
      result = removeQuestionEcho(result, userQuestion)
    }

    // 性能监控：dev 环境下记录慢调用
    const elapsedMs = performance.now() - startTime
    if (elapsedMs > PERFORMANCE_WARN_THRESHOLD_MS && import.meta.env.DEV) {
      console.warn(
        `[contentFilter] Slow filter: ${elapsedMs.toFixed(2)}ms for ${raw.length} chars`,
      )
    }

    return result
  } catch (err) {
    // 错误边界：返回原始输入，确保流式渲染不被中断
    if (import.meta.env.DEV) {
      console.error('[contentFilter] Filter failed, returning raw input:', err)
    }
    return raw
  }
}

/**
 * Minimum overlap ratio to consider as a question echo.
 * If less than this ratio of the user question matches, we don't treat it as echo.
 */
const ECHO_MIN_RATIO = 0.6

/**
 * Remove question echo from the beginning of assistant content.
 *
 * DeerFlow agent often outputs the user's question verbatim at the start of the
 * response (sometimes twice — before and after the memory block). After the
 * memory block is filtered out, we may see:
 *   "用户问题\n\n用户问题\n\n实际回答内容"
 * or just:
 *   "用户问题\n\n实际回答内容"
 *
 * This function detects if the assistant content starts with the user question
 * and removes the echo prefix, keeping only the actual answer.
 *
 * @param content - Filtered assistant content (after pattern-based filters)
 * @param userQuestion - The user's original question text
 * @returns Content with question echo removed
 */
export function removeQuestionEcho(content: string, userQuestion: string): string {
  if (!content || !userQuestion) return content

  // Normalize both texts for comparison: collapse whitespace, trim
  const normalize = (s: string) => s.replace(/\s+/g, ' ').trim()
  const normQuestion = normalize(userQuestion)

  // If the question is empty after normalization, nothing to remove
  if (!normQuestion) return content

  // Loop to remove ALL consecutive question echoes
  // DeerFlow agent may output the question multiple times (before and after memory block)
  let result = content
  let maxIterations = 5 // Safety limit to prevent infinite loops

  while (maxIterations > 0) {
    const normResult = normalize(result)

    // If the question is longer than the remaining content, no more echoes possible
    if (normQuestion.length > normResult.length) break

    // Check if remaining content starts with the full question
    if (normResult.startsWith(normQuestion)) {
      const echoEnd = findEchoEndPosition(result, userQuestion)
      if (echoEnd > 0) {
        result = result.slice(echoEnd).trim()
        maxIterations--
        continue // Check for another consecutive echo
      }
    }

    // Partial match: check if a significant prefix of the question matches
    // (handles cases where the echo is slightly truncated)
    const minLen = Math.ceil(normQuestion.length * ECHO_MIN_RATIO)
    let foundPartial = false
    for (let len = normQuestion.length - 1; len >= minLen && !foundPartial; len--) {
      const partialQuestion = normQuestion.slice(0, len)
      if (normResult.startsWith(partialQuestion)) {
        // Pass partialQuestion (not full userQuestion) to find where THIS partial prefix ends
        const echoEnd = findEchoEndPosition(result, partialQuestion)
        if (echoEnd > 0) {
          result = result.slice(echoEnd).trim()
          foundPartial = true
          maxIterations--
        }
      }
    }

    // No echo found at start, stop looping
    if (!foundPartial) break
  }

  return result || content // Return result, fallback to original if empty
}

/**
 * Find the position in the original content where the question echo ends.
 * Uses fuzzy matching to handle whitespace differences between the echo and the
 * actual user question.
 */
function findEchoEndPosition(content: string, userQuestion: string): number {
  // Strategy: walk through both strings character by character, skipping
  // whitespace differences, to find where the echo ends in the content
  let ci = 0 // content index
  let qi = 0 // question index

  while (ci < content.length && qi < userQuestion.length) {
    const cChar = content[ci]
    const qChar = userQuestion[qi]

    if (cChar === qChar) {
      ci++
      qi++
    } else if (isWhitespace(cChar) && isWhitespace(qChar)) {
      // Both are whitespace (may differ), skip both
      ci = skipWhitespace(content, ci)
      qi = skipWhitespace(userQuestion, qi)
    } else if (isWhitespace(cChar)) {
      // Extra whitespace in content
      ci = skipWhitespace(content, ci)
    } else if (isWhitespace(qChar)) {
      // Extra whitespace in question
      qi = skipWhitespace(userQuestion, qi)
    } else {
      // Mismatch - not an echo
      return -1
    }
  }

  // If we consumed the entire question, the echo ends at current content position
  if (qi >= userQuestion.length) {
    // Skip trailing whitespace/newlines after the echo
    let end = ci
    while (end < content.length && /\s/.test(content[end])) {
      end++
    }
    return end
  }

  return -1
}

function isWhitespace(c: string): boolean {
  return /\s/.test(c)
}

function skipWhitespace(s: string, i: number): number {
  while (i < s.length && /\s/.test(s[i])) i++
  return i
}

/**
 * 采用 deerflow 的 stripInternalMarkers 函数
 * 移除所有已知后端注入的标记标签
 *
 * 参考：deer-flow-reference/frontend/src/core/messages/utils.ts
 *
 * 用于导出路径等场景，确保内部标记不会泄漏到用户可见的内容中。
 *
 * @param content - 原始内容字符串
 * @returns 清理后的内容
 */
export function stripInternalMarkers(content: string): string {
  if (!content) return ''
  let result = content.replace(INTERNAL_MARKER_RE, '')
  result = result.replace(UNCLOSED_MARKER_RE, '')
  return result.trim()
}

/**
 * Export the internal marker tags for use in other modules
 * (e.g., message classification, event normalizer)
 */
export { INTERNAL_MARKER_TAGS }