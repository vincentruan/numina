<template>
  <div class="allocation-treemap">
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { TreemapChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { CallbackDataParams } from 'echarts/types/dist/shared'
import type { AllocationItem } from '@/types'
import { useCurrency } from '@/composables/useCurrency'

use([CanvasRenderer, TreemapChart, TooltipComponent])

const { format } = useCurrency()

const props = defineProps<{
  data: AllocationItem[]
}>()

const isDark = ref(document.documentElement.getAttribute('data-theme') === 'dark')

let observer: MutationObserver | null = null
onMounted(() => {
  observer = new MutationObserver(() => {
    isDark.value = document.documentElement.getAttribute('data-theme') === 'dark'
  })
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})
onUnmounted(() => observer?.disconnect())

// Parse a hex color to [r, g, b]
function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace('#', '')
  const full = clean.length === 3
    ? clean.split('').map(c => c + c).join('')
    : clean
  if (!/^[0-9a-fA-F]{6}$/.test(full)) throw new Error(`Invalid hex: ${hex}`)
  const n = parseInt(full, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

// Convert RGB to HSL
function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  const rn = r / 255, gn = g / 255, bn = b / 255
  const max = Math.max(rn, gn, bn), min = Math.min(rn, gn, bn)
  const l = (max + min) / 2
  if (max === min) return [0, 0, l]
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h: number
  if (max === rn) h = ((gn - bn) / d + (gn < bn ? 6 : 0)) / 6
  else if (max === gn) h = ((bn - rn) / d + 2) / 6
  else h = ((rn - gn) / d + 4) / 6
  return [h * 360, s, l]
}

// Convert HSL back to hex
function hslToHex(h: number, s: number, l: number): string {
  const hn = h / 360
  const hue2rgb = (p: number, q: number, t: number) => {
    let tt = t
    if (tt < 0) tt += 1
    if (tt > 1) tt -= 1
    if (tt < 1 / 6) return p + (q - p) * 6 * tt
    if (tt < 1 / 2) return q
    if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6
    return p
  }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s
  const p = 2 * l - q
  const r = Math.round(hue2rgb(p, q, hn + 1 / 3) * 255)
  const g = Math.round(hue2rgb(p, q, hn) * 255)
  const b = Math.round(hue2rgb(p, q, hn - 1 / 3) * 255)
  return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('')
}

// Mute a color for dark mode: reduce saturation, shift lightness to mid-range
function mutedColor(hex: string): string {
  try {
    const [r, g, b] = hexToRgb(hex)
    const [h, s, l] = rgbToHsl(r, g, b)
    // Reduce saturation to ~50%, clamp lightness to 30–45% range for dark bg
    const newS = Math.min(s, 0.55)
    const newL = Math.max(0.28, Math.min(l * 0.7, 0.42))
    return hslToHex(h, newS, newL)
  } catch {
    return hex
  }
}

const chartOption = computed(() => {
  const borderColor = isDark.value ? '#0d0d1f' : '#fff'
  const labelColor = isDark.value ? '#e8e8f0' : '#fff'
  const tooltipBg = isDark.value ? '#1a1a2e' : '#fff'
  const tooltipText = isDark.value ? '#d0d0e8' : '#333'
  const tooltipBorder = isDark.value ? '#2a2a4a' : '#e0e0e0'

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: tooltipBg,
      borderColor: tooltipBorder,
      textStyle: { color: tooltipText, fontSize: 12 },
      formatter: (params: CallbackDataParams) => {
        const item = props.data.find(d => d.category_name === params.name)
        if (item) {
          return `${params.name}: ${format(Number(params.value))} (${item.percentage.toFixed(1)}%)`
        }
        return `${params.name}: ${format(Number(params.value))}`
      },
    },
    series: [
      {
        type: 'treemap',
        left: 0,
        top: 0,
        right: 0,
        bottom: 0,
        width: '100%',
        height: '100%',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: {
          show: true,
          formatter: (params: CallbackDataParams) => {
            const item = props.data.find(d => d.category_name === params.name)
            if (item) {
              return `${params.name}\n${item.percentage.toFixed(1)}%`
            }
            return params.name
          },
          fontSize: 12,
          color: labelColor,
          overflow: 'truncate',
        },
        upperLabel: { show: false },
        itemStyle: {
          borderWidth: 2,
          borderColor,
          gapWidth: 2,
        },
        visibleMin: 100,
        data: props.data.map(item => ({
          name: item.category_name,
          value: item.amount,
          itemStyle: {
            color: isDark.value ? mutedColor(item.color) : item.color,
          },
        })),
      },
    ],
  }
})
</script>

<style scoped>
.allocation-treemap {
  /* Stretch to fill the collapse content area, overriding its 12px side padding */
  width: calc(100% + 24px);
  margin: 0 -12px;
}

.chart {
  width: 100%;
  height: clamp(180px, 55vw, 300px);
  display: block;
}
</style>
