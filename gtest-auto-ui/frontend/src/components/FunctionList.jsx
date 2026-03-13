import React, { useState, useContext } from 'react'
import {
  Input,
  Tag,
  Typography,
  Space,
  Empty,
  Collapse,
  Badge,
  Button,
  Divider,
  theme,
} from 'antd'
import {
  SearchOutlined,
  FunctionOutlined,
  HistoryOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import { AppContext } from '../context/AppContext'

const { Text } = Typography
const { Panel } = Collapse

function formatTimestamp(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ts
  }
}

function getKindColor(kind) {
  const map = {
    integer: 'blue',
    float: 'cyan',
    bool: 'purple',
    pointer: 'orange',
    array: 'green',
    struct: 'gold',
    enum: 'magenta',
    void: 'default',
    reference: 'geekblue',
  }
  return map[kind] || 'default'
}

export default function FunctionList() {
  const {
    parseResult,
    selectedFunctions,
    selectSingleFunction,
    toggleSelectedFunction,
    history,
    setCurrentRun,
    setStep,
  } = useContext(AppContext)
  const { token } = theme.useToken()

  const [search, setSearch] = useState('')

  const functions = parseResult?.functions || []

  const filtered = functions.filter((f) =>
    f.name.toLowerCase().includes(search.toLowerCase())
  )

  const isSelected = (func) => selectedFunctions.some((f) => f.name === func.name)

  const handleClick = (e, func) => {
    if (e.ctrlKey || e.metaKey) {
      toggleSelectedFunction(func)
    } else {
      selectSingleFunction(func)
    }
  }

  const handleHistoryClick = (item) => {
    setCurrentRun({
      run_id: item.run_id,
      status: 'done',
      logs: [],
      result: item.result || item,
    })
    setStep(5)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Search */}
      <div style={{ padding: '12px 12px 8px' }}>
        <Input
          prefix={<SearchOutlined style={{ color: token.colorTextQuaternary }} />}
          placeholder="搜索函数名..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
          size="small"
        />
      </div>

      <Divider style={{ margin: '0 0 4px' }} />

      {/* Function list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
        {functions.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无函数"
            style={{ margin: '32px 0' }}
          />
        ) : filtered.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="无匹配结果"
            style={{ margin: '32px 0' }}
          />
        ) : (
          filtered.map((func) => {
            const selected = isSelected(func)
            return (
              <div
                key={func.name}
                onClick={(e) => handleClick(e, func)}
                style={{
                  padding: '8px 10px',
                  marginBottom: 4,
                  borderRadius: token.borderRadius,
                  border: `1.5px solid ${
                    selected ? token.colorPrimary : token.colorBorderSecondary
                  }`,
                  background: selected
                    ? token.colorPrimaryBg
                    : token.colorBgContainer,
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                  userSelect: 'none',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <FunctionOutlined
                    style={{
                      color: selected ? token.colorPrimary : token.colorTextTertiary,
                      fontSize: 12,
                    }}
                  />
                  <Text
                    strong
                    style={{
                      fontSize: 13,
                      color: selected ? token.colorPrimary : token.colorText,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      flex: 1,
                    }}
                    title={func.name}
                  >
                    {func.name}
                  </Text>
                </div>
                <Space size={4} wrap>
                  <Tag
                    color={getKindColor(func.return_type?.kind)}
                    style={{ fontSize: 11, margin: 0 }}
                  >
                    {func.return_type?.raw || func.return_type?.kind || 'void'}
                  </Tag>
                  <Tag style={{ fontSize: 11, margin: 0 }}>
                    {func.params?.length || 0} 参数
                  </Tag>
                </Space>
              </div>
            )
          })
        )}
      </div>

      {/* History section */}
      {history.length > 0 && (
        <>
          <Divider style={{ margin: '4px 0 0' }} />
          <div style={{ padding: '8px', maxHeight: 200, overflowY: 'auto' }}>
            <Collapse
              size="small"
              ghost
              items={[
                {
                  key: 'history',
                  label: (
                    <Space>
                      <HistoryOutlined />
                      <Text style={{ fontSize: 12 }}>历史记录 ({history.length})</Text>
                    </Space>
                  ),
                  children: history.map((item, idx) => {
                    const passed = item.passed ?? item.result?.summary?.passed ?? 0
                    const failed = item.failed ?? item.result?.summary?.failed ?? 0
                    const total = item.total ?? (passed + failed)
                    const status = failed === 0 ? 'success' : 'error'
                    return (
                      <div
                        key={item.run_id || idx}
                        onClick={() => handleHistoryClick(item)}
                        style={{
                          padding: '6px 8px',
                          marginBottom: 4,
                          borderRadius: 4,
                          border: `1px solid ${token.colorBorderSecondary}`,
                          cursor: 'pointer',
                          background: token.colorBgLayout,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Badge status={status} />
                          <Text style={{ fontSize: 11, color: token.colorTextSecondary }}>
                            {formatTimestamp(item.timestamp)}
                          </Text>
                        </div>
                        <Space size={4} style={{ marginTop: 2 }}>
                          <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 11 }} />
                          <Text style={{ fontSize: 11 }}>{passed}</Text>
                          <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 11 }} />
                          <Text style={{ fontSize: 11 }}>{failed}</Text>
                          <Text style={{ fontSize: 11, color: token.colorTextTertiary }}>
                            / {total}
                          </Text>
                        </Space>
                      </div>
                    )
                  }),
                },
              ]}
            />
          </div>
        </>
      )}
    </div>
  )
}
