import type { SpotTheMistakeChallenge } from '@/types/learning-challenge'

export const spotTheMistakeEnglish: SpotTheMistakeChallenge = {
  id: 'mistake-english-grammar',
  topicId: 'mt_scBgiMKhG_',
  type: 'spot-the-mistake',
  difficulty: 2,
  ageGroup: 'mid',
  scenario: 'Can you find the wrong sentence?',
  scenarioZh: '你能找到出错的句子吗？',
  discoveryMessage: 'English is tricky — good eye!',
  discoveryMessageZh: '英语真难——眼力不错！',
  lines: ['She go to school every day.', 'He reads a book after lunch.', 'They play football at recess.'],
  linesZh: ['她每天上学。', '他午饭后看书。', '他们课间踢足球。'],
  mistakeLineIndex: 0,
}

export const spotTheMistakeLearning: SpotTheMistakeChallenge = {
  id: 'mistake-study-habit',
  topicId: 'mt_mvXufozy2s',
  type: 'spot-the-mistake',
  difficulty: 1,
  ageGroup: 'early',
  scenario: 'A classmate shares their study plan. Which step is wrong?',
  scenarioZh: '同学分享了他的学习计划，哪一步有问题？',
  discoveryMessage: 'You spotted it!',
  discoveryMessageZh: '你找到啦！',
  lines: [
    '1. Read the chapter quietly.',
    '2. Take notes while reading.',
    '3. Never look at the notes again.',
  ],
  mistakeLineIndex: 2,
}
