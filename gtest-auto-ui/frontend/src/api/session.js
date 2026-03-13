import axios from 'axios'

const BASE = '/api/v1'

export const createSession = () => axios.post(`${BASE}/session`)

export const uploadFiles = (sessionId, formData) =>
  axios.post(`${BASE}/session/${sessionId}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

export const getHistory = (sessionId) =>
  axios.get(`${BASE}/session/${sessionId}/history`)
