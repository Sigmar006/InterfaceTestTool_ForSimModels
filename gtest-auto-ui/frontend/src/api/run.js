import axios from 'axios'

const BASE = '/api/v1'

export const startRun = (sessionId, payload) =>
  axios.post(`${BASE}/session/${sessionId}/run`, payload)

export const getResult = (runId) =>
  axios.get(`${BASE}/run/${runId}/result`)
