/**
 * 文件类型检测和图标映射
 *
 * 参考: frontend/src/core/utils/files.tsx
 */

// 扩展名 → 语言字符串（用于代码高亮）
export const EXTENSION_MAP: Record<string, string> = {
  // Web
  js: 'javascript',
  jsx: 'javascript',
  ts: 'typescript',
  tsx: 'typescript',
  vue: 'vue',
  html: 'html',
  css: 'css',
  scss: 'scss',
  less: 'less',
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',

  // Backend
  py: 'python',
  rb: 'ruby',
  go: 'go',
  rs: 'rust',
  java: 'java',
  kt: 'kotlin',
  php: 'php',
  cs: 'csharp',
  cpp: 'cpp',
  c: 'c',
  h: 'c',

  // Shell
  sh: 'bash',
  bash: 'bash',
  zsh: 'bash',
  ps1: 'powershell',

  // Config
  toml: 'toml',
  ini: 'ini',
  env: 'dotenv',
  dockerfile: 'dockerfile',
  makefile: 'makefile',

  // Data
  csv: 'csv',
  sql: 'sql',
  xml: 'xml',
  md: 'markdown',
  markdown: 'markdown',

  // Default
  txt: 'text',
}

// 扩展名 → 图标名称（lucide iconify 格式）
export const FILE_ICON_MAP: Record<string, string> = {
  // Code
  js: 'lucide:file-code',
  jsx: 'lucide:file-code',
  ts: 'lucide:file-code',
  tsx: 'lucide:file-code',
  vue: 'lucide:file-code',
  py: 'lucide:file-code',
  go: 'lucide:file-code',
  rs: 'lucide:file-code',
  java: 'lucide:file-code',
  rb: 'lucide:file-code',
  php: 'lucide:file-code',
  c: 'lucide:file-code',
  cpp: 'lucide:file-code',
  h: 'lucide:file-code',
  cs: 'lucide:file-code',
  sh: 'lucide:file-terminal',
  bash: 'lucide:file-terminal',
  zsh: 'lucide:file-terminal',

  // Web
  html: 'lucide:file-code',
  css: 'lucide:file-code',
  scss: 'lucide:file-code',
  less: 'lucide:file-code',
  json: 'lucide:file-json',
  yaml: 'lucide:file-code',
  yml: 'lucide:file-code',
  xml: 'lucide:file-code',

  // Documents
  md: 'lucide:file-text',
  markdown: 'lucide:file-text',
  txt: 'lucide:file-text',
  pdf: 'lucide:file-text',
  doc: 'lucide:file-text',
  docx: 'lucide:file-text',

  // Images
  png: 'lucide:file-image',
  jpg: 'lucide:file-image',
  jpeg: 'lucide:file-image',
  gif: 'lucide:file-image',
  webp: 'lucide:file-image',
  svg: 'lucide:file-image',
  ico: 'lucide:file-image',

  // Config
  toml: 'lucide:file-cog',
  ini: 'lucide:file-cog',
  env: 'lucide:file-cog',
  dockerfile: 'lucide:file-cog',
  makefile: 'lucide:file-cog',

  // Skill
  skill: 'lucide:file-code',

  // Default (unknown file type)
  default: 'lucide:file',
}

/**
 * 获取文件名（不含路径）
 */
export function getFileName(filepath: string): string {
  const parts = filepath.split('/')
  const raw = parts[parts.length - 1] || filepath
  // Decode URI-encoded characters (e.g. Chinese filenames from href)
  try {
    return decodeURIComponent(raw)
  } catch {
    return raw
  }
}

/**
 * 获取文件扩展名
 */
export function getFileExtension(filepath: string): string {
  const filename = getFileName(filepath)
  const dotIndex = filename.lastIndexOf('.')
  if (dotIndex === -1 || dotIndex === 0) return ''
  return filename.slice(dotIndex + 1).toLowerCase()
}

/**
 * 检查是否为代码文件
 */
export function isCodeFile(filepath: string): boolean {
  const ext = getFileExtension(filepath)
  return EXTENSION_MAP[ext] !== undefined && ext !== 'md' && ext !== 'txt'
}

/**
 * 获取文件语言（用于代码高亮）
 */
export function getFileLanguage(filepath: string): string {
  const ext = getFileExtension(filepath)
  return EXTENSION_MAP[ext] || 'text'
}

/**
 * 获取文件图标
 */
export function getFileIcon(filepath: string): string {
  const ext = getFileExtension(filepath)
  return FILE_ICON_MAP[ext] || FILE_ICON_MAP['default']
}

/**
 * 检查是否为图片文件
 */
export function isImageFile(filepath: string): boolean {
  const ext = getFileExtension(filepath)
  return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'bmp'].includes(ext)
}

/**
 * 检查是否为 Markdown 文件
 */
export function isMarkdownFile(filepath: string): boolean {
  const ext = getFileExtension(filepath)
  return ext === 'md' || ext === 'markdown'
}

/**
 * 检查是否为 HTML 文件（需要 sandbox iframe）
 */
export function isHtmlFile(filepath: string): boolean {
  const ext = getFileExtension(filepath)
  return ext === 'html' || ext === 'htm'
}

/**
 * 检查是否为 PDF 文件
 */
export function isPdfFile(filepath: string): boolean {
  return getFileExtension(filepath) === 'pdf'
}

/**
 * 检查是否为 Skill 文件（DeerFlow skill installation）
 */
export function isSkillFile(filepath: string): boolean {
  return getFileExtension(filepath) === 'skill'
}