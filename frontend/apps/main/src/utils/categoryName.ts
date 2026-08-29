import i18n from '@/i18n'

/**
 * Default category translation keys.
 *
 * System categories are seeded by the backend with canonical Chinese names
 * (`_CATEGORY_IDENTITIES` in `server/apps/backend/app/bootstrap/categories.py`).
 * The frontend maps those Chinese seed names to `categoryNames.*` i18n keys so
 * the UI renders them in the active locale. If a name is unknown (e.g. a new
 * system category added later, or a user-created custom category), it falls back
 * to the raw name.
 */
const SYSTEM_CATEGORY_KEYS: Record<string, string> = {
  房产: 'realEstate',
  车辆: 'vehicle',
  数码: 'digital',
  家电: 'appliance',
  家具: 'furniture',
  珠宝: 'jewelry',
  服饰: 'clothing',
  美妆: 'beauty',
  运动: 'sports',
  玩具: 'toys',
  宠物: 'pets',
  乐器: 'musicalInstruments',
  箱包: 'bags',
  奢侈品: 'luxury',
  其他: 'other',
  存款: 'deposits',
  基金: 'funds',
  股票: 'stocks',
  债券: 'bonds',
  保险: 'insurance',
  理财产品: 'wealthManagement',
  数字货币: 'digitalCurrency',
  其他金融: 'otherFinancial',
}

type CategoryNameInput = { name: string; is_system?: boolean }

/**
 * Return a category's localized display name.
 *
 * System categories are translated via `categoryNames.*` keys; custom
 * categories (`is_system === false`) keep their user-entered name. When
 * `is_system` is absent (e.g. `CategoryInfo`), translation is attempted by name
 * and falls back to the raw name if no key matches.
 */
export function getCategoryName(category: CategoryNameInput): string {
  if (category.is_system === false) return category.name

  const key = SYSTEM_CATEGORY_KEYS[category.name]
  if (key) {
    const path = `categoryNames.${key}`
    if (i18n.global.te(path)) return i18n.global.t(path)
  }
  return category.name
}
