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

// 扩展名 → 图标名称
export const FILE_ICON_MAP: Record<string, string> = {
  // Code
  js: 'file-code',
  jsx: 'file-code',
  ts: 'file-code',
  tsx: 'file-code',
  vue: 'file-code',
  py: 'file-code',
  go: 'file-code',
  rs: 'file-code',
  java: 'file-code',
  rb: 'file-code',
  php: 'file-code',
  c: 'file-code',
  cpp: 'file-code',
  h: 'file-code',
  cs: 'file-code',
  sh: 'terminal',
  bash: 'terminal',
  zsh: 'terminal',

  // Web
  html: 'file-code',
  css: 'file-code',
  scss: 'file-code',
  less: 'file-code',
  json: 'file-json',
  yaml: 'file-yaml',
  yml: 'file-yaml',
  xml: 'file-code',

  // Documents
  md: 'file-markdown',
  markdown: 'file-markdown',
  txt: 'file-text',
  pdf: 'file-pdf',
  doc: 'file-document',
  docx: 'file-document',

  // Images
  png: 'file-image',
  jpg: 'file-image',
  jpeg: 'file-image',
  gif: 'file-image',
  webp: 'file-image',
  svg: 'file-image',
  ico: 'file-image',

  // Config
  toml: 'file-config',
  ini: 'file-config',
  env: 'file-config',
  dockerfile: 'docker',
  makefile: 'file-config',

  // Skill
  skill: 'file-skill',

  // Default
  default: 'file',
}

/**
 * 获取文件名（不含路径）
 */
export function getFileName(filepath: string): string {
  const parts = filepath.split('/')
  return parts[parts.length - 1] || filepath
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