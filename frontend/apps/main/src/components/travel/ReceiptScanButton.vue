<template>
  <div class="receipt-scan-button">
    <van-uploader
      v-model="fileList"
      :max-count="1"
      :after-read="onFileRead"
      :before-read="beforeRead"
      accept="image/*"
      capture="environment"
    >
      <van-button type="primary" plain block round :loading="uploading">
        <van-icon name="photograph" />
        {{ uploading ? t('travel.receiptScanning') : t('travel.photoReceipt') }}
      </van-button>
    </van-uploader>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showFailToast } from 'vant'
import { uploadReceipt } from '@/api/travel'

const props = defineProps<{
  tripId: string
}>()

const { t } = useI18n()
const router = useRouter()

import type { UploaderFileListItem } from 'vant'

const fileList = ref<UploaderFileListItem[]>([])
const uploading = ref(false)

function beforeRead(file: File | File[]): boolean {
  const files = Array.isArray(file) ? file : [file]
  const isValid = files.every(f => f.type.startsWith('image/'))
  if (!isValid) {
    showFailToast('请上传图片文件')
    return false
  }
  return true
}

async function onFileRead(file: UploaderFileListItem | UploaderFileListItem[]) {
  uploading.value = true
  try {
    const fileObj = Array.isArray(file) ? file[0]?.file : file.file
    if (!fileObj) return
    const res = await uploadReceipt(props.tripId, fileObj)
    const imageUrl = res.data.receipt_image_url

    // Navigate to expense form with pre-filled receipt URL
    router.push({
      path: `/travel/${props.tripId}/expense/new`,
      query: { receipt_image_url: imageUrl },
    })
  } catch {
    showFailToast(t('travel.receiptUploadFailed'))
  } finally {
    uploading.value = false
    fileList.value = []
  }
}
</script>

<style scoped>
.receipt-scan-button {
  width: 100%;
}
</style>
