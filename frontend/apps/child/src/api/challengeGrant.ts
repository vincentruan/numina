import http from './index'
import type { ChallengeGrant, ChildChallenge, ChallengeCreateRequest } from '@/types/challengeGrant'

export async function getActiveChildChallenges(): Promise<ChildChallenge[]> {
  const res = await http.get('/child/challenges/active')
  return res.data.items
}

export async function listFamilyChallenges(): Promise<ChallengeGrant[]> {
  const res = await http.get('/challenges')
  return res.data.items
}

export async function createChallenge(req: ChallengeCreateRequest): Promise<ChallengeGrant> {
  const res = await http.post('/challenges', req)
  return res.data
}

export async function cancelChallenge(challengeId: string): Promise<ChallengeGrant> {
  const res = await http.post(`/challenges/${challengeId}/cancel`)
  return res.data
}