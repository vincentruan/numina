export interface CoinTier {
  gold: number
  silver: number
  copper: number
}

/**
 * 将总铜币数转换为金银铜组合
 * @param totalCopper 总铜币数
 * @param copperToSilver 铜→银兑换比例（默认10）
 * @param silverToGold 银→金兑换比例（默认10）
 */
export function splitCoinTiers(
  totalCopper: number,
  copperToSilver = 10,
  silverToGold = 10,
): CoinTier {
  const copperPerGold = copperToSilver * silverToGold
  const gold = Math.floor(totalCopper / copperPerGold)
  const remaining = totalCopper % copperPerGold
  const silver = Math.floor(remaining / copperToSilver)
  const copper = remaining % copperToSilver
  return { gold, silver, copper }
}

/**
 * 格式化显示（只显示非零面值）
 * 例：{ gold: 1, silver: 2, copper: 5 } → "1金 2银 5铜"
 */
export function formatCoinTiers(tiers: CoinTier): string {
  const parts: string[] = []
  if (tiers.gold > 0) parts.push(`${tiers.gold}金`)
  if (tiers.silver > 0) parts.push(`${tiers.silver}银`)
  if (tiers.copper > 0 || parts.length === 0) parts.push(`${tiers.copper}铜`)
  return parts.join(' ')
}
