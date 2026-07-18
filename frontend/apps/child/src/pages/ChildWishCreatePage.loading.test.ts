import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import ChildWishCreatePage from './ChildWishCreatePage.vue'
import { globalLoadingCount, completeGlobalLoading } from '@/composables/usePageLoading'
import * as wishesApi from '@/api/childWishes'

vi.mock('@/api/childWishes')

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      common: { back: '返回' },
      wishes: {
        createPageTitle: '新建心愿',
        wishNameLabel: '名称',
        wishNamePlaceholder: '',
        emojiLabel: '',
        emojiPlaceholder: '',
        descLabel: '',
        descPlaceholder: '',
        priorityLabel: '',
        priorityHigh: '高',
        priorityMedium: '中',
        priorityLow: '低',
        emojiPickerTitle: '',
        submitBtn: '提交',
        submitSuccess: '成功',
        continueCreate: '继续许愿',
        backToList: '返回列表',
      },
      toast: { submitFailed: '失败' },
    },
  },
})

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/wishes/new', name: 'ChildWishCreate', component: { template: '<div />' } },
      { path: '/wishes', name: 'ChildWishes', component: { template: '<div />' } },
    ],
  })
}

async function mountCreate() {
  const router = makeRouter()
  await router.push({ name: 'ChildWishCreate' })
  await router.isReady()
  const wrapper = mount(ChildWishCreatePage, {
    global: {
      plugins: [i18n, router],
      // Do NOT stub VanButton/VanDialog — we need their real @click / @confirm
      // behavior to exercise submitWish() + "continue creating" end-to-end.
      stubs: {
        VanField: {
          template: '<input class="van-field" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          props: ['modelValue', 'placeholder', 'type', 'label', 'disabled', 'maxlength'],
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('ChildWishCreatePage — does not leak loading state across "continue creating"', () => {
  beforeEach(() => {
    completeGlobalLoading()
    vi.mocked(wishesApi.createChildWish).mockResolvedValue({} as unknown as wishesApi.ChildWish)
  })

  it('onMounted complete() leaves globalLoadingCount at 0', async () => {
    await mountCreate()
    expect(globalLoadingCount.value).toBe(0)
  })

  it('after submit, loading state stays at 0 (no stuck spinner on this non-skeleton page)', async () => {
    const wrapper = await mountCreate()

    // Fill required field (wish name) and submit
    await wrapper.find('input').setValue('Lego')
    await wrapper.find('.btn-submit').trigger('click')
    await flushPromises()

    // submitWish() ran; complete() in onMounted already balanced the router's
    // NProgress.start(). The page neither increments nor leaves loading running.
    expect(wishesApi.createChildWish).toHaveBeenCalledTimes(1)
    expect(globalLoadingCount.value).toBe(0)

    // "Continue creating" only resets the form; it must not perturb loading.
    // (resetAndContinue touches no loading API — assert it stays at 0.)
    const dialogComp = wrapper.findComponent({ name: 'VanDialog' })
    if (dialogComp.exists()) {
      await dialogComp.vm.$emit('confirm')
      await flushPromises()
    }
    expect(globalLoadingCount.value).toBe(0)
  })
})
