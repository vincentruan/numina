import html2canvas from 'html2canvas'
import type { Asset } from '@/types'
import { formatCurrency, formatDate } from './format'

/**
 * 生成单个资产卡片图片
 */
export async function generateAssetCard(asset: Asset): Promise<Blob> {
  // 创建临时容器
  const container = document.createElement('div')
  container.style.cssText = `
    position: fixed;
    left: -9999px;
    top: 0;
    width: 750px;
    height: 1000px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 40px;
    box-sizing: border-box;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  `

  // 计算使用天数
  const purchaseDate = new Date(asset.purchase_date)
  const today = new Date()
  const daysUsed = Math.floor((today.getTime() - purchaseDate.getTime()) / (1000 * 60 * 60 * 24))

  // 构建卡片内容
  container.innerHTML = `
    <div style="
      background: white;
      border-radius: 24px;
      padding: 32px;
      height: 100%;
      display: flex;
      flex-direction: column;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    ">
      <!-- 资产图片/图标 -->
      <div style="
        width: 100%;
        height: 300px;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 24px;
        overflow: hidden;
      ">
        ${asset.image_url
          ? `<img src="${asset.image_url}" style="width: 100%; height: 100%; object-fit: cover;" />`
          : `<div style="font-size: 120px;">${asset.category?.icon || '📦'}</div>`
        }
      </div>

      <!-- 资产名称 -->
      <h2 style="
        font-size: 36px;
        font-weight: bold;
        color: #1a1a1a;
        margin: 0 0 12px 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      ">${asset.name}</h2>

      <!-- 分类标签 -->
      <div style="
        display: inline-block;
        background: #667eea;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 20px;
        margin-bottom: 24px;
        align-self: flex-start;
      ">
        ${asset.category?.icon || ''} ${asset.category?.name || '未分类'}
      </div>

      <!-- 数据网格 -->
      <div style="
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        margin-bottom: 24px;
        flex: 1;
      ">
        <div style="
          background: #f8f9fa;
          padding: 20px;
          border-radius: 12px;
        ">
          <div style="font-size: 18px; color: #666; margin-bottom: 8px;">购入价格</div>
          <div style="font-size: 28px; font-weight: bold; color: #1a1a1a;">
            ${formatCurrency(asset.purchase_price)}
          </div>
        </div>

        <div style="
          background: #f8f9fa;
          padding: 20px;
          border-radius: 12px;
        ">
          <div style="font-size: 18px; color: #666; margin-bottom: 8px;">当前价值</div>
          <div style="font-size: 28px; font-weight: bold; color: #1a1a1a;">
            ${formatCurrency(asset.current_value)}
          </div>
        </div>

        <div style="
          background: #fff3e0;
          padding: 20px;
          border-radius: 12px;
        ">
          <div style="font-size: 18px; color: #666; margin-bottom: 8px;">日均成本</div>
          <div style="font-size: 28px; font-weight: bold; color: #f57c00;">
            ${asset.daily_cost ? formatCurrency(asset.daily_cost) : '¥0.00'}
          </div>
        </div>

        <div style="
          background: #f8f9fa;
          padding: 20px;
          border-radius: 12px;
        ">
          <div style="font-size: 18px; color: #666; margin-bottom: 8px;">使用天数</div>
          <div style="font-size: 28px; font-weight: bold; color: #1a1a1a;">
            ${daysUsed} 天
          </div>
        </div>
      </div>

      <!-- 购入日期 -->
      <div style="
        font-size: 18px;
        color: #666;
        margin-bottom: 24px;
      ">
        购入日期：${formatDate(asset.purchase_date)}
      </div>

      <!-- 品牌水印 -->
      <div style="
        text-align: center;
        padding-top: 20px;
        border-top: 2px solid #f0f0f0;
      ">
        <div style="
          font-size: 24px;
          font-weight: bold;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        ">Numina</div>
        <div style="font-size: 16px; color: #999; margin-top: 4px;">
          数字家庭资产管理
        </div>
      </div>
    </div>
  `

  document.body.appendChild(container)

  try {
    const canvas = await html2canvas(container, {
      scale: 2,
      backgroundColor: null,
      logging: false,
    })

    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (blob) {
          resolve(blob)
        } else {
          reject(new Error('Failed to generate image'))
        }
      }, 'image/png')
    })
  } finally {
    document.body.removeChild(container)
  }
}

/**
 * 生成多资产汇总图
 */
export async function generateSummaryCard(assets: Asset[]): Promise<Blob> {
  // 计算汇总数据
  const totalValue = assets.reduce((sum, asset) => sum + asset.current_value, 0)
  const totalDailyCost = assets.reduce((sum, asset) => sum + (asset.daily_cost || 0), 0)

  // 按分类统计
  const categoryStats = new Map<string, { name: string; icon: string; count: number }>()
  assets.forEach(asset => {
    const categoryName = asset.category?.name || '未分类'
    const categoryIcon = asset.category?.icon || '📦'
    const existing = categoryStats.get(categoryName)
    if (existing) {
      existing.count++
    } else {
      categoryStats.set(categoryName, { name: categoryName, icon: categoryIcon, count: 1 })
    }
  })

  // 创建临时容器
  const container = document.createElement('div')
  container.style.cssText = `
    position: fixed;
    left: -9999px;
    top: 0;
    width: 750px;
    height: 1000px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 40px;
    box-sizing: border-box;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  `

  // 构建分类列表 HTML
  const categoryListHTML = Array.from(categoryStats.values())
    .map(cat => `
      <div style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 0;
        border-bottom: 1px solid #f0f0f0;
      ">
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="font-size: 32px;">${cat.icon}</span>
          <span style="font-size: 22px; color: #1a1a1a;">${cat.name}</span>
        </div>
        <span style="
          font-size: 24px;
          font-weight: bold;
          color: #667eea;
        ">${cat.count} 项</span>
      </div>
    `)
    .join('')

  container.innerHTML = `
    <div style="
      background: white;
      border-radius: 24px;
      padding: 40px;
      height: 100%;
      display: flex;
      flex-direction: column;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    ">
      <!-- 标题 -->
      <h1 style="
        font-size: 48px;
        font-weight: bold;
        text-align: center;
        margin: 0 0 40px 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      ">我的资产汇总</h1>

      <!-- 汇总数据卡片 -->
      <div style="
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin-bottom: 32px;
      ">
        <div style="
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          padding: 24px;
          border-radius: 16px;
          color: white;
        ">
          <div style="font-size: 20px; opacity: 0.9; margin-bottom: 8px;">资产总数</div>
          <div style="font-size: 48px; font-weight: bold;">${assets.length}</div>
          <div style="font-size: 18px; opacity: 0.8; margin-top: 4px;">项</div>
        </div>

        <div style="
          background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
          padding: 24px;
          border-radius: 16px;
          color: white;
        ">
          <div style="font-size: 20px; opacity: 0.9; margin-bottom: 8px;">总价值</div>
          <div style="font-size: 36px; font-weight: bold;">
            ${formatCurrency(totalValue)}
          </div>
        </div>
      </div>

      <!-- 日均成本 -->
      <div style="
        background: #fff3e0;
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 32px;
      ">
        <div style="font-size: 20px; color: #666; margin-bottom: 8px;">日均成本汇总</div>
        <div style="font-size: 40px; font-weight: bold; color: #f57c00;">
          ${formatCurrency(totalDailyCost)}
        </div>
      </div>

      <!-- 分类分布 -->
      <div style="flex: 1; overflow: hidden;">
        <h3 style="
          font-size: 28px;
          font-weight: bold;
          color: #1a1a1a;
          margin: 0 0 20px 0;
        ">分类分布</h3>
        <div style="max-height: 300px; overflow-y: auto;">
          ${categoryListHTML}
        </div>
      </div>

      <!-- 品牌水印 -->
      <div style="
        text-align: center;
        padding-top: 24px;
        margin-top: 24px;
        border-top: 2px solid #f0f0f0;
      ">
        <div style="
          font-size: 28px;
          font-weight: bold;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        ">Numina</div>
        <div style="font-size: 18px; color: #999; margin-top: 4px;">
          数字家庭资产管理
        </div>
      </div>
    </div>
  `

  document.body.appendChild(container)

  try {
    const canvas = await html2canvas(container, {
      scale: 2,
      backgroundColor: null,
      logging: false,
    })

    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (blob) {
          resolve(blob)
        } else {
          reject(new Error('Failed to generate image'))
        }
      }, 'image/png')
    })
  } finally {
    document.body.removeChild(container)
  }
}

/**
 * 下载图片到本地
 */
export function downloadImage(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
