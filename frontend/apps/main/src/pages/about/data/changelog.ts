export interface ChangelogEntry {
  version: string
  date: string
  changes: string[] // i18n keys, resolved at render time via t()
}

export const changelog: ChangelogEntry[] = [
  {
    version: '1.0.0',
    date: '2026-10-16',
    changes: [
      'settings.changelogV1_1',
      'settings.changelogV1_2',
      'settings.changelogV1_3',
      'settings.changelogV1_4',
      'settings.changelogV1_5',
      'settings.changelogV1_6',
      'settings.changelogV1_7',
    ],
  },
]
