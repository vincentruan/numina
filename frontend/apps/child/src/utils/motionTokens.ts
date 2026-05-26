export const MOTION = {
  durations: {
    instant: 100,
    fast: 200,
    medium: 400,
    slow: 800,
    glacial: 3000,
  },
  easings: {
    standardOut: 'cubic-bezier(0.0, 0.0, 0.2, 1)',
    standardInOut: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
    springPop: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
    accelerate: 'cubic-bezier(0.4, 0.0, 1, 1)',
  },
  scales: {
    press: 0.96,
    pulse: 1.03,
    pop: 1.15,
    burst: 1.2,
  },
  haptic: {
    landing: [50, 30, 50, 30, 100],
    confirm: [50],
    arrival: [400],
    final: [150],
    rewardPulse: [50, 30, 50],
  },
} as const
