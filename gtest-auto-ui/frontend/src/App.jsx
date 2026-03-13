import React, { useState, useContext } from 'react'
import { Layout, Steps, Button, Drawer, Typography, Space, theme } from 'antd'
import { SettingOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { AppContext } from './context/AppContext'
import FileUploader from './components/FileUploader'
import FunctionList from './components/FunctionList'
import ParamForm from './components/ParamForm'
import ResultPanel from './components/ResultPanel'
import Settings from './components/Settings'

const { Header, Content } = Layout
const { Title } = Typography

const STEPS = [
  { title: '上传文件' },
  { title: '解析接口' },
  { title: '配置参数' },
  { title: '运行测试' },
  { title: '查看结果' },
]

export default function App() {
  const { step, uploadedFiles } = useContext(AppContext)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const { token } = theme.useToken()

  const showUploader = step === 1 || uploadedFiles.length === 0

  return (
    <Layout style={{ minHeight: '100vh', background: token.colorBgLayout }}>
      {/* Header */}
      <Header
        style={{
          background: token.colorBgContainer,
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          gap: 32,
          position: 'sticky',
          top: 0,
          zIndex: 100,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        }}
      >
        {/* Logo */}
        <Space align="center" style={{ flexShrink: 0 }}>
          <ThunderboltOutlined style={{ fontSize: 22, color: token.colorPrimary }} />
          <Title level={5} style={{ margin: 0, color: token.colorText, whiteSpace: 'nowrap' }}>
            GTest Auto UI
          </Title>
        </Space>

        {/* Steps */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <Steps
            current={step - 1}
            items={STEPS}
            size="small"
            style={{ maxWidth: 720 }}
          />
        </div>

        {/* Settings button */}
        <Button
          icon={<SettingOutlined />}
          type="text"
          onClick={() => setSettingsOpen(true)}
          style={{ flexShrink: 0 }}
        >
          设置
        </Button>
      </Header>

      {/* Main content */}
      <Content style={{ padding: '16px', overflow: 'auto' }}>
        {showUploader ? (
          <FileUploader />
        ) : (
          <div
            style={{
              display: 'flex',
              gap: 16,
              height: 'calc(100vh - 96px)',
              alignItems: 'stretch',
            }}
          >
            {/* Left: FunctionList */}
            <div
              style={{
                width: 240,
                flexShrink: 0,
                background: token.colorBgContainer,
                borderRadius: token.borderRadius,
                border: `1px solid ${token.colorBorderSecondary}`,
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <FunctionList />
            </div>

            {/* Center: ParamForm */}
            <div
              style={{
                flex: 1,
                background: token.colorBgContainer,
                borderRadius: token.borderRadius,
                border: `1px solid ${token.colorBorderSecondary}`,
                overflow: 'auto',
              }}
            >
              <ParamForm />
            </div>

            {/* Right: ResultPanel */}
            <div
              style={{
                width: 360,
                flexShrink: 0,
                background: token.colorBgContainer,
                borderRadius: token.borderRadius,
                border: `1px solid ${token.colorBorderSecondary}`,
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <ResultPanel />
            </div>
          </div>
        )}
      </Content>

      {/* Settings Drawer */}
      <Settings open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </Layout>
  )
}
