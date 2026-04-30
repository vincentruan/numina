import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'vant/lib/index.css'
import '@vant/touch-emulator'
import './style.css'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { useCurrencyStore } from './stores/currency'
import http from './api/index'
import { configureAuthHttp } from '@numina/auth'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(i18n)

// Wire up shared auth package with this app's HTTP client
configureAuthHttp(http)

// Fetch currencies on app init
const currencyStore = useCurrencyStore()
currencyStore.fetchCurrencies()

app.mount('#app')
