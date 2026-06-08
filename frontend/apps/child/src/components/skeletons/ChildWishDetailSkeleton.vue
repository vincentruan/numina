<template>
  <div class="wish-detail-skeleton">
    <!-- PageHeader skeleton -->
    <PageHeaderSkeleton />

    <!-- Wish card skeleton -->
    <WishCardSkeleton />
  </div>
</template>

<script setup lang="ts">
import PageHeaderSkeleton from './PageHeaderSkeleton.vue'
import WishCardSkeleton from './WishCardSkeleton.vue'
// Skeleton for ChildWishDetailPage
</script>

<style scoped>
.wish-detail-skeleton {
  background: var(--color-canvas);
  min-height: 100vh;
  padding: var(--space-md);
}
</style>