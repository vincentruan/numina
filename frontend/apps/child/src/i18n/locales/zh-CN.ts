// Child app i18n — zh-CN
// Includes child-specific keys and error code mappings from @numina/auth

export default {
  common: {
    confirm: '确认',
    cancel: '取消',
    back: '返回',
    loading: '加载中...',
    error: '出错了',
    retry: '重试',
  },
  nav: {
    home: '首页',
    tasks: '任务',
    ledger: '账本',
    wishes: '心愿',
    treasures: '宝藏',
  },
  auth: {
    selectChild: '选择小朋友',
    enterPin: '输入密码',
    returnToAdult: '返回大人模式',
    enterParentPassword: '请输入家长密码',
    bindTitle: '绑定账号',
  },
  errors: {
    PIN_ERROR: '❌ PIN错误，请重试',
    ACCOUNT_LOCKED: '🔒 账号已锁定，请让爸爸妈妈帮你解锁',
    INVALID_CREDENTIALS: '❌ 用户名或密码错误',
    AUTH_INVALID_CREDENTIALS: '❌ 用户名或密码错误',
    AUTH_CHILD_NOT_FOUND: '❌ 孩子不存在',
    AUTH_PIN_LOCKED: '🔒 PIN已锁定，请稍后再试',
    CHILD_NOT_FOUND: '❌ 孩子不存在',
    COIN_INSUFFICIENT: '⚠️ 余额不足',
    WISH_INSUFFICIENT_COINS: '⚠️ 积分不足，无法兑现',
    wrongPassword: '❌ 密码错误，请重试',
  },
  toast: {
    loginSuccess: '✅ 登录成功',
    logoutSuccess: '✅ 已退出',
    loginFailedGeneric: '❌ 登录失败，请重试',
    noPasskey: '⚠️ 未注册面容/指纹，请使用图形密码',
    verifyFailed: '❌ 验证失败，请重试',
  },
}
