<template>
  <van-tabbar v-model="active" route>
    <van-tabbar-item to="/" icon="chart-trending-o">总览</van-tabbar-item>
    <van-tabbar-item to="/assets" icon="balance-o">资产</van-tabbar-item>
    <van-tabbar-item to="/assets/new" icon="add-o">
      <template #icon="{ active: isActive }">
        <div class="add-btn" :class="{ active: isActive }">
          <van-icon name="plus" size="24" />
        </div>
      </template>
      <span></span>
    </van-tabbar-item>
    <van-tabbar-item to="/liabilities" icon="bill-o">负债</van-tabbar-item>
    <van-tabbar-item to="/family" icon="friends-o">家庭</van-tabbar-item>
  </van-tabbar>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const active = ref(0)
</script>

<style scoped>
.add-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #1989fa;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: -10px;
  color: #fff;
  box-shadow: 0 2px 8px rgba(25, 137, 250, 0.4);
}
.add-btn.active {
  background: #0d7de8;
}
</style>
