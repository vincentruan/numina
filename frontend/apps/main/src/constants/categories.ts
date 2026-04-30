/**
 * System categories as compile-time constants.
 *
 * 21 system categories (13 physical + 8 financial) seeded on app startup.
 * These never change at runtime, so using constants eliminates API calls.
 */

import type { Category } from '@/types'

export const SYSTEM_CATEGORIES: Category[] = [
  // Physical assets (13)
  {
    id: 'sys-cat-001',
    family_id: null,
    name: '房产',
    icon: 'icon-home',
    color: '#EF4444',
    asset_type: 'physical',
    sort_order: 1,
    is_system: true,
  },
  {
    id: 'sys-cat-002',
    family_id: null,
    name: '车辆',
    icon: 'icon-car',
    color: '#F97316',
    asset_type: 'physical',
    sort_order: 2,
    is_system: true,
  },
  {
    id: 'sys-cat-003',
    family_id: null,
    name: '数码',
    icon: 'icon-digital',
    color: '#3B82F6',
    asset_type: 'physical',
    sort_order: 3,
    is_system: true,
  },
  {
    id: 'sys-cat-004',
    family_id: null,
    name: '家电',
    icon: 'icon-appliance',
    color: '#8B5CF6',
    asset_type: 'physical',
    sort_order: 4,
    is_system: true,
  },
  {
    id: 'sys-cat-005',
    family_id: null,
    name: '家具',
    icon: 'icon-furniture',
    color: '#A855F7',
    asset_type: 'physical',
    sort_order: 5,
    is_system: true,
  },
  {
    id: 'sys-cat-006',
    family_id: null,
    name: '珠宝',
    icon: 'icon-jewelry',
    color: '#EC4899',
    asset_type: 'physical',
    sort_order: 6,
    is_system: true,
  },
  {
    id: 'sys-cat-007',
    family_id: null,
    name: '服饰',
    icon: 'icon-clothing',
    color: '#14B8A6',
    asset_type: 'physical',
    sort_order: 7,
    is_system: true,
  },
  {
    id: 'sys-cat-008',
    family_id: null,
    name: '美妆',
    icon: 'icon-beauty',
    color: '#F43F5E',
    asset_type: 'physical',
    sort_order: 8,
    is_system: true,
  },
  {
    id: 'sys-cat-009',
    family_id: null,
    name: '运动',
    icon: 'icon-sports',
    color: '#22C55E',
    asset_type: 'physical',
    sort_order: 9,
    is_system: true,
  },
  {
    id: 'sys-cat-010',
    family_id: null,
    name: '玩具',
    icon: 'icon-toys',
    color: '#6366F1',
    asset_type: 'physical',
    sort_order: 10,
    is_system: true,
  },
  {
    id: 'sys-cat-011',
    family_id: null,
    name: '宠物',
    icon: 'icon-pets',
    color: '#D97706',
    asset_type: 'physical',
    sort_order: 11,
    is_system: true,
  },
  {
    id: 'sys-cat-012',
    family_id: null,
    name: '乐器',
    icon: 'icon-music',
    color: '#7C3AED',
    asset_type: 'physical',
    sort_order: 12,
    is_system: true,
  },
  {
    id: 'sys-cat-013',
    family_id: null,
    name: '箱包',
    icon: 'icon-bags',
    color: '#BE185D',
    asset_type: 'physical',
    sort_order: 13,
    is_system: true,
  },
  // Financial assets (8)
  {
    id: 'sys-cat-014',
    family_id: null,
    name: '存款',
    icon: 'icon-deposit',
    color: '#0EA5E9',
    asset_type: 'financial',
    sort_order: 14,
    is_system: true,
  },
  {
    id: 'sys-cat-015',
    family_id: null,
    name: '基金',
    icon: 'icon-fund',
    color: '#10B981',
    asset_type: 'financial',
    sort_order: 15,
    is_system: true,
  },
  {
    id: 'sys-cat-016',
    family_id: null,
    name: '股票',
    icon: 'icon-stock',
    color: '#EF4444',
    asset_type: 'financial',
    sort_order: 16,
    is_system: true,
  },
  {
    id: 'sys-cat-017',
    family_id: null,
    name: '债券',
    icon: 'icon-bond',
    color: '#F59E0B',
    asset_type: 'financial',
    sort_order: 17,
    is_system: true,
  },
  {
    id: 'sys-cat-018',
    family_id: null,
    name: '保险',
    icon: 'icon-insurance',
    color: '#6366F1',
    asset_type: 'financial',
    sort_order: 18,
    is_system: true,
  },
  {
    id: 'sys-cat-019',
    family_id: null,
    name: '理财产品',
    icon: 'icon-wealth',
    color: '#8B5CF6',
    asset_type: 'financial',
    sort_order: 19,
    is_system: true,
  },
  {
    id: 'sys-cat-020',
    family_id: null,
    name: '数字货币',
    icon: 'icon-crypto',
    color: '#F97316',
    asset_type: 'financial',
    sort_order: 20,
    is_system: true,
  },
  {
    id: 'sys-cat-021',
    family_id: null,
    name: '其他金融',
    icon: 'icon-other-finance',
    color: '#64748B',
    asset_type: 'financial',
    sort_order: 21,
    is_system: true,
  },
]

/**
 * Filter system categories by asset type
 */
export function getSystemCategoriesByType(assetType: 'physical' | 'financial'): Category[] {
  return SYSTEM_CATEGORIES.filter((cat) => cat.asset_type === assetType)
}

/**
 * Get a system category by its ID
 */
export function getSystemCategoryById(id: string): Category | undefined {
  return SYSTEM_CATEGORIES.find((cat) => cat.id === id)
}

/**
 * Get a system category by its name
 */
export function getSystemCategoryByName(name: string): Category | undefined {
  return SYSTEM_CATEGORIES.find((cat) => cat.name === name)
}

/**
 * Check if a category ID is a system category
 */
export function isSystemCategory(id: string): boolean {
  return id.startsWith('sys-cat-')
}