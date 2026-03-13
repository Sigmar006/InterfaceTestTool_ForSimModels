import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'

const SETTINGS_KEY = 'gtest-auto-ui-settings'

const defaultSettings = {
  cmake_path: 'cmake',
  build_type: 'Debug',
  cpp_standard: '17',
  test_timeout: 30,
  gtest_version: '1.14.0',
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (raw) {
      return { ...defaultSettings, ...JSON.parse(raw) }
    }
  } catch (e) {
    // ignore
  }
  return { ...defaultSettings }
}

export const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [sessionId, setSessionId] = useState(null)
  const [parseResult, setParseResult] = useState(null)
  const [selectedFunctions, setSelectedFunctionsState] = useState([])
  const [currentRun, setCurrentRun] = useState(null)
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [settings, setSettings] = useState(loadSettings)
  const [history, setHistory] = useState([])
  const [step, setStep] = useState(1)

  // Persist settings to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
    } catch (e) {
      // ignore
    }
  }, [settings])

  const toggleSelectedFunction = useCallback((func) => {
    setSelectedFunctionsState((prev) => {
      const exists = prev.find((f) => f.name === func.name)
      if (exists) {
        return prev.filter((f) => f.name !== func.name)
      }
      return [...prev, func]
    })
  }, [])

  const selectSingleFunction = useCallback((func) => {
    setSelectedFunctionsState([func])
  }, [])

  const updateSettings = useCallback((updates) => {
    setSettings((prev) => ({ ...prev, ...updates }))
  }, [])

  const addHistory = useCallback((runSummary) => {
    setHistory((prev) => [runSummary, ...prev])
  }, [])

  const value = {
    sessionId,
    setSessionId,
    parseResult,
    setParseResult,
    selectedFunctions,
    setSelectedFunctions: setSelectedFunctionsState,
    toggleSelectedFunction,
    selectSingleFunction,
    currentRun,
    setCurrentRun,
    uploadedFiles,
    setUploadedFiles,
    settings,
    updateSettings,
    history,
    addHistory,
    step,
    setStep,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useAppContext() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useAppContext must be used within AppProvider')
  return ctx
}
