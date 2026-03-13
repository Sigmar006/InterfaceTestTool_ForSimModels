import React, { useContext, useState, useEffect, useRef, useCallback } from 'react'
import { Collapse, Typography, Spin, Alert, Tag, theme } from 'antd'
import { LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { useWebSocket } from '../../hooks/useWebSocket'
import { AppContext } from '../../context/AppContext'

const { Text } = Typography

const STAGE_LABELS = {
  configure: 'CMake 配置',
  build: '编译构建',
  test: '运行测试',
}

function LogLine({ line }) {
  const isStderr = line.stream === 'stderr' || line.level === 'error'
  return (
    <div
      style={{
        background: isStderr ? '#fff1f0' : 'transparent',
        borderLeft: isStderr ? '2px solid #ff4d4f' : '2px solid transparent',
        padding: '1px 6px',
        fontFamily: 'monospace',
        fontSize: 12,
        color: isStderr ? '#cf1322' : '#262626',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all',
        lineHeight: '1.5',
      }}
    >
      {line.text || line.message || line}
    </div>
  )
}

export default function LogView({ runId }) {
  const { setCurrentRun, addHistory, setStep } = useContext(AppContext)
  const { token } = theme.useToken()

  // stages: { [stageName]: { lines: [], status: 'running'|'done'|'error' } }
  const [stages, setStages] = useState({})
  const [stageOrder, setStageOrder] = useState([])
  const [currentStage, setCurrentStage] = useState(null)
  const [activeKeys, setActiveKeys] = useState([])
  const [wsError, setWsError] = useState(null)
  const logBottomRef = useRef(null)

  const handleMessage = useCallback(
    (msg) => {
      switch (msg.type) {
        case 'stage_start': {
          const stageName = msg.stage
          setStages((prev) => ({
            ...prev,
            [stageName]: { lines: [], status: 'running' },
          }))
          setStageOrder((prev) =>
            prev.includes(stageName) ? prev : [...prev, stageName]
          )
          setCurrentStage(stageName)
          setActiveKeys((prev) =>
            prev.includes(stageName) ? prev : [...prev, stageName]
          )
          break
        }
        case 'log': {
          const stageName = msg.stage || currentStage
          if (!stageName) break
          setStages((prev) => {
            const stage = prev[stageName] || { lines: [], status: 'running' }
            return {
              ...prev,
              [stageName]: {
                ...stage,
                lines: [...stage.lines, { text: msg.text || msg.message, stream: msg.stream }],
              },
            }
          })
          break
        }
        case 'stage_done': {
          const stageName = msg.stage
          setStages((prev) => ({
            ...prev,
            [stageName]: {
              ...(prev[stageName] || { lines: [] }),
              status: msg.success === false ? 'error' : 'done',
            },
          }))
          // Collapse completed stages
          setActiveKeys((prev) => prev.filter((k) => k !== stageName))
          break
        }
        case 'done': {
          const result = msg.result || msg.data
          setCurrentRun((prev) => ({
            ...prev,
            status: 'done',
            result,
          }))
          if (result) {
            const summary = result.summary || {}
            addHistory({
              run_id: runId,
              timestamp: new Date().toISOString(),
              passed: summary.passed || 0,
              failed: summary.failed || 0,
              total: summary.total || 0,
              result,
            })
          }
          setStep(5)
          break
        }
        case 'error': {
          setWsError(msg.message || msg.error || '运行出错')
          setCurrentRun((prev) => ({ ...prev, status: 'error' }))
          break
        }
        default:
          break
      }
    },
    [currentStage, runId, setCurrentRun, addHistory, setStep]
  )

  const { connected, error: wsConnError } = useWebSocket(runId, handleMessage)

  // Auto-scroll
  useEffect(() => {
    logBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [stages])

  const stageStatusIcon = (status) => {
    if (status === 'running') return <LoadingOutlined spin style={{ color: token.colorPrimary }} />
    if (status === 'done') return <CheckCircleOutlined style={{ color: '#52c41a' }} />
    if (status === 'error') return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
    return null
  }

  const collapseItems = stageOrder.map((stageName) => {
    const stage = stages[stageName] || { lines: [], status: 'running' }
    return {
      key: stageName,
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {stageStatusIcon(stage.status)}
          <Text strong style={{ fontSize: 13 }}>
            {STAGE_LABELS[stageName] || stageName}
          </Text>
          <Tag
            color={
              stage.status === 'done'
                ? 'success'
                : stage.status === 'error'
                ? 'error'
                : 'processing'
            }
            style={{ fontSize: 11 }}
          >
            {stage.status === 'done'
              ? '完成'
              : stage.status === 'error'
              ? '失败'
              : '进行中'}
          </Tag>
          <Text style={{ fontSize: 11, color: token.colorTextTertiary }}>
            {stage.lines.length} 行
          </Text>
        </span>
      ),
      children: (
        <div
          style={{
            maxHeight: 300,
            overflowY: 'auto',
            background: '#fafafa',
            borderRadius: 4,
            padding: 4,
          }}
        >
          {stage.lines.map((line, i) => (
            <LogLine key={i} line={line} />
          ))}
        </div>
      ),
    }
  })

  return (
    <div style={{ padding: 12, overflowY: 'auto', height: '100%' }}>
      {/* Connection status */}
      {!connected && !wsConnError && stageOrder.length === 0 && (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin indicator={<LoadingOutlined />} tip="连接到运行日志..." />
        </div>
      )}

      {(wsError || wsConnError) && (
        <Alert
          type="error"
          message={wsError || wsConnError}
          style={{ marginBottom: 12 }}
          showIcon
        />
      )}

      {collapseItems.length > 0 && (
        <Collapse
          activeKey={activeKeys}
          onChange={setActiveKeys}
          items={collapseItems}
          size="small"
        />
      )}

      {/* Spinner at bottom */}
      {currentStage && stages[currentStage]?.status === 'running' && (
        <div
          style={{
            textAlign: 'center',
            padding: '16px 0',
            color: token.colorTextSecondary,
            fontSize: 13,
          }}
        >
          <Spin
            indicator={<LoadingOutlined />}
            style={{ marginRight: 8 }}
          />
          {STAGE_LABELS[currentStage] || currentStage} 进行中...
        </div>
      )}

      <div ref={logBottomRef} />
    </div>
  )
}
