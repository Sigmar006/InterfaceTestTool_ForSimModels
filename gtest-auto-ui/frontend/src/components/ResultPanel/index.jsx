import React, { useContext } from 'react'
import { Tabs, Empty, Typography, theme } from 'antd'
import { FileTextOutlined, CheckSquareOutlined } from '@ant-design/icons'
import { AppContext } from '../../context/AppContext'
import LogView from './LogView'
import ResultSummary from './ResultSummary'

const { Text } = Typography

export default function ResultPanel() {
  const { currentRun } = useContext(AppContext)
  const { token } = theme.useToken()

  if (!currentRun) {
    return (
      <div
        style={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: 8,
          padding: 24,
        }}
      >
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <span>
              运行测试后，
              <br />
              日志和结果将在此显示
            </span>
          }
        />
      </div>
    )
  }

  const isDone = currentRun.status === 'done'
  const hasResult = !!currentRun.result
  const isRunning = currentRun.status === 'running' || currentRun.status === 'pending'

  // If running: show only logs
  // If done: show both tabs, default to result if available
  if (isRunning && !hasResult) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div
          style={{
            padding: '8px 12px',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            background: token.colorFillTertiary,
          }}
        >
          <Text strong style={{ fontSize: 13 }}>
            <FileTextOutlined style={{ marginRight: 6 }} />
            实时日志
          </Text>
        </div>
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <LogView runId={currentRun.run_id} />
        </div>
      </div>
    )
  }

  const tabItems = [
    {
      key: 'log',
      label: (
        <span>
          <FileTextOutlined />
          日志
        </span>
      ),
      children: (
        <div style={{ height: 'calc(100vh - 200px)', overflowY: 'auto' }}>
          <LogView runId={currentRun.run_id} />
        </div>
      ),
    },
    {
      key: 'result',
      label: (
        <span>
          <CheckSquareOutlined />
          结果
        </span>
      ),
      children: (
        <div style={{ height: 'calc(100vh - 200px)', overflowY: 'auto' }}>
          <ResultSummary result={currentRun.result} />
        </div>
      ),
    },
  ]

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Tabs
        defaultActiveKey={hasResult ? 'result' : 'log'}
        items={tabItems}
        size="small"
        style={{ flex: 1 }}
        tabBarStyle={{
          padding: '0 12px',
          marginBottom: 0,
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
        }}
      />
    </div>
  )
}
