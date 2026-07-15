/**
 * DeerFlow 私有思考标签处理
 *
 * 参考: frontend/src/core/messages/utils.ts splitInlineReasoning()
 *
 * 安全规则:
 * - 剥离 `<think>...</think>` 标签（标准格式，后端 llm.py 使用）
 * - 剥离 `halle_think_start...halle_think_end` 标签（旧格式，向后兼容）
 * - 处理流式场景：只有开标签无闭标签时，后续内容视为推理
 * - 如果后端返回 `additional_kwargs.reasoning_content`，优先使用（这是安全摘要）
 */

const THINK_OPEN_TAG = '<think>'
const THINK_CLOSE_TAG = '</think>'
const LEGACY_THINK_OPEN_TAG = 'halle_think_start'
const LEGACY_THINK_CLOSE_TAG = 'halle_think_end'

// 正则：匹配完整的思考标签块（标准 + 旧格式）
const THINK_TAG_RE = new RegExp(
  `(?:${THINK_OPEN_TAG}|${LEGACY_THINK_OPEN_TAG})\\s*([\\s\\S]*?)\\s*(?:${THINK_CLOSE_TAG}|${LEGACY_THINK_CLOSE_TAG})`,
  'g',
)

/**
 * 分离推理内容和正文内容
 *
 * @param content - 原始内容
 * @returns 分离后的推理和正文
 */
export function splitInlineReasoning(content: string): {
  content: string
  reasoning: string | null
} {
  if (!content) {
    return { content: '', reasoning: null }
  }

  const reasoningParts: string[] = []

  // 第一遍：剥离所有完整的思考标签并收集推理内容
  let cleaned = content.replace(THINK_TAG_RE, (_, reasoning: string) => {
    const normalized = reasoning.trim()
    if (normalized) {
      reasoningParts.push(normalized)
    }
    return ''
  })

  // 流式安全处理：只有开标签时，后续内容视为推理中
  // 避免未闭合的推理内容渲染到正文
  // 支持两种标签格式：<think> 和 halle_think_start
  const openTags = [THINK_OPEN_TAG, LEGACY_THINK_OPEN_TAG]
  const closeTags = [THINK_CLOSE_TAG, LEGACY_THINK_CLOSE_TAG]

  for (let i = 0; i < openTags.length; i++) {
    const openTag = openTags[i]
    const closeTag = closeTags[i]
    const openTagIndex = cleaned.indexOf(openTag)

    if (openTagIndex !== -1) {
      // 排除 markdown inline code 内的标签（用户讨论标签本身）
      // 检查开标签前是否是反引号
      if (openTagIndex > 0 && cleaned[openTagIndex - 1] === '`') {
        // 在 inline code 内，不处理
        continue
      }

      const tail = cleaned.slice(openTagIndex + openTag.length).trim()
      if (tail) {
        // 尝试找到闭标签
        const closeIndex = tail.indexOf(closeTag)
        if (closeIndex !== -1) {
          // 有闭标签，提取内容
          const innerContent = tail.slice(0, closeIndex).trim()
          if (innerContent) {
            reasoningParts.push(innerContent)
          }
          cleaned = cleaned.slice(0, openTagIndex) + tail.slice(closeIndex + closeTag.length)
        } else {
          // 无闭标签，视为正在推理中
          reasoningParts.push(tail)
          cleaned = cleaned.slice(0, openTagIndex)
        }
      } else {
        // 只有开标签，移除
        cleaned = cleaned.slice(0, openTagIndex)
      }
      break // 找到并处理了一个标签，退出循环
    }
  }

  return {
    content: cleaned.trim(),
    reasoning: reasoningParts.length > 0 ? reasoningParts.join('\n\n') : null,
  }
}

/**
 * 从 AI 消息提取推理内容（安全摘要优先）
 *
 * 优先级:
 * 1. additional_kwargs.reasoning_content（后端安全摘要）
 * 2. content 数组中的 thinking 类型块（Anthropic gateway）
 * 3. 字符串 content 中的思考标签内容
 *
 * @param message - 消息对象
 * @returns 推理内容或 null
 */
export function extractReasoningContentFromMessage(message: {
  type?: string
  role?: string
  content?: string | unknown[] | null
  additional_kwargs?: Record<string, unknown> | null
}): string | null {
  if (message.type !== 'ai' && message.role !== 'assistant') {
    return null
  }

  // 后端安全摘要优先
  if (message.additional_kwargs?.reasoning_content) {
    return message.additional_kwargs.reasoning_content as string
  }

  // Anthropic gateway thinking block
  if (Array.isArray(message.content)) {
    for (const part of message.content) {
      if (part && typeof part === 'object' && (part as { type?: string }).type === 'thinking') {
        return (part as { thinking?: string }).thinking as string
      }
    }
  }

  // 字符串 content 中的思考标签
  if (typeof message.content === 'string') {
    return splitInlineReasoning(message.content).reasoning
  }

  return null
}

/**
 * 从消息提取正文内容（剥离推理标签）
 *
 * @param message - 消息对象
 * @returns 正文内容
 */
export function extractContentFromMessage(message: {
  type?: string
  role?: string
  content?: string | unknown[] | null
}): string {
  if (typeof message.content === 'string') {
    const { content } = splitInlineReasoning(message.content)
    return content ?? message.content.trim()
  }

  if (Array.isArray(message.content)) {
    return message.content
      .map((part) => {
        if (typeof part === 'string') return part
        if (part && typeof part === 'object') {
          const p = part as { type?: string; text?: string; image_url?: { url?: string } }
          if (p.type === 'text' && p.text) return p.text
          if (p.type === 'image_url' && p.image_url?.url) return `![image](${p.image_url.url})`
        }
        return ''
      })
      .join('\n')
      .trim()
  }

  return ''
}

/**
 * 检查是否有推理内容
 *
 * @param message - 消息对象
 * @returns 是否有推理
 */
export function hasReasoning(message: {
  type?: string
  role?: string
  content?: string | unknown[] | null
  additional_kwargs?: Record<string, unknown> | null
}): boolean {
  return extractReasoningContentFromMessage(message) !== null
}

/**
 * 检查是否有正文内容
 *
 * @param message - 消息对象
 * @returns 是否有正文
 */
export function hasContent(message: {
  type?: string
  role?: string
  content?: string | unknown[] | null
}): boolean {
  const content = extractContentFromMessage(message)
  return content.length > 0
}