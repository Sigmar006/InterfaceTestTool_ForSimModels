import axios from 'axios'

const BASE = '/api/v1'

export const parseHeader = (sessionId, payload) =>
  axios.post(`${BASE}/session/${sessionId}/parse`, payload)
