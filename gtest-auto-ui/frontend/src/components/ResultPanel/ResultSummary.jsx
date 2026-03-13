import React, { useState } from 'react'
import {
  Card,
  Statistic,
  List,
  Collapse,
  Tag,
  Typography,
  Space,
  Empty,
  Row,
  Col,
  theme,
  Badge,
} from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'

const { Text, Title } = Typography

function formatDuration(ms) {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function TestCaseItem({ testCase }) {
  const { token } = theme.useToken()
  const passed = testCase.status === 'passed' || testCase.passed === true
  const failed = testCase.status === 'failed' || testCase.passed === false

  const statusIcon = passed ? (
    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
  ) : (
    <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 16 }} />
  )

  const details = []

  if (testCase.stdout_captured) {
    details.push(
      <div key="stdout">
        <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          标准输出:
        </Text>
        <SyntaxHighlighter
          language="text"
          style={oneLight}
          customStyle={{
            fontSize: 12,
            borderRadius: 4,
            maxHeight: 200,
            overflowY: 'auto',
            margin: 0,
          }}
        >
          {testCase.stdout_captured}
        </SyntaxHighlighter>
      </div>
    )
  }

  if (testCase.failure_message) {
    details.push(
      <div key="failure">
        <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4, color: '#cf1322' }}>
          失败信息:
        </Text>
        <SyntaxHighlighter
          language="text"
          style={oneLight}
          customStyle={{
            fontSize: 12,
            borderRadius: 4,
            maxHeight: 200,
            overflowY: 'auto',
            margin: 0,
            background: '#fff1f0',
          }}
        >
          {testCase.failure_message}
        </SyntaxHighlighter>
      </div>
    )
  }

  if (testCase.return_value !== undefined && testCase.return_value !== null) {
    details.push(
      <div key="return">
        <Text strong style={{ fontSize: 12 }}>返回值: </Text>
        <Text
          code
          style={{ fontSize: 12 }}
        >
          {String(testCase.return_value)}
        </Text>
      </div>
    )
  }

  const header = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
      {statusIcon}
      <Text
        strong
        style={{
          fontSize: 13,
          color: passed ? '#389e0d' : '#cf1322',
          flex: 1,
        }}
      >
        {testCase.test_id || testCase.function_name || testCase.name || 'Test'}
      </Text>
      {testCase.function_name && testCase.test_id !== testCase.function_name && (
        <Tag style={{ fontSize: 11 }}>{testCase.function_name}</Tag>
      )}
      <Space style={{ marginLeft: 'auto' }}>
        <ClockCircleOutlined style={{ fontSize: 11, color: token.colorTextTertiary }} />
        <Text style={{ fontSize: 11, color: token.colorTextTertiary }}>
          {formatDuration(testCase.duration_ms || testCase.duration)}
        </Text>
      </Space>
    </div>
  )

  if (details.length === 0) {
    return (
      <List.Item>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
          {statusIcon}
          <Text strong style={{ fontSize: 13, flex: 1 }}>
            {testCase.test_id || testCase.function_name || testCase.name || 'Test'}
          </Text>
          <Text style={{ fontSize: 11, color: token.colorTextTertiary }}>
            {formatDuration(testCase.duration_ms || testCase.duration)}
          </Text>
        </div>
      </List.Item>
    )
  }

  return (
    <List.Item style={{ padding: 0 }}>
      <Collapse
        ghost
        style={{ width: '100%' }}
        items={[
          {
            key: testCase.test_id || testCase.name || 'item',
            label: header,
            children: (
              <Space direction="vertical" style={{ width: '100%' }}>
                {details}
              </Space>
            ),
          },
        ]}
      />
    </List.Item>
  )
}

export default function ResultSummary({ result }) {
  const { token } = theme.useToken()

  if (!result) {
    return (
      <div style={{ padding: 16 }}>
        <Empty description="暂无结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    )
  }

  const summary = result.summary || {}
  const testCases = result.test_cases || result.results || []
  const passed = summary.passed ?? testCases.filter((t) => t.status === 'passed' || t.passed === true).length
  const failed = summary.failed ?? testCases.filter((t) => t.status === 'failed' || t.passed === false).length
  const total = summary.total ?? testCases.length
  const duration = summary.duration_ms || summary.duration || result.duration_ms

  const allPassed = failed === 0

  return (
    <div style={{ padding: 12 }}>
      {/* Overall status */}
      <div
        style={{
          background: allPassed ? '#f6ffed' : '#fff2f0',
          border: `1px solid ${allPassed ? '#b7eb8f' : '#ffccc7'}`,
          borderRadius: token.borderRadius,
          padding: '12px 16px',
          marginBottom: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        {allPassed ? (
          <CheckCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />
        ) : (
          <CloseCircleOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
        )}
        <div>
          <Text
            strong
            style={{ fontSize: 15, color: allPassed ? '#389e0d' : '#cf1322' }}
          >
            {allPassed ? '全部通过' : '存在失败'}
          </Text>
          <br />
          <Text style={{ fontSize: 12, color: token.colorTextSecondary }}>
            {passed}/{total} 通过
            {duration != null && ` · 耗时 ${formatDuration(duration)}`}
          </Text>
        </div>
      </div>

      {/* Statistics */}
      <Row gutter={8} style={{ marginBottom: 12 }}>
        <Col span={8}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic
              value={passed}
              valueStyle={{ color: '#52c41a', fontSize: 22 }}
              prefix={<CheckCircleOutlined />}
              title={<span style={{ fontSize: 11 }}>通过</span>}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic
              value={failed}
              valueStyle={{ color: '#ff4d4f', fontSize: 22 }}
              prefix={<CloseCircleOutlined />}
              title={<span style={{ fontSize: 11 }}>失败</span>}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic
              value={total}
              valueStyle={{ fontSize: 22 }}
              title={<span style={{ fontSize: 11 }}>总计</span>}
            />
          </Card>
        </Col>
      </Row>

      {/* Test cases */}
      {testCases.length > 0 ? (
        <List
          size="small"
          dataSource={testCases}
          renderItem={(tc) => <TestCaseItem key={tc.test_id || tc.name} testCase={tc} />}
          style={{
            border: `1px solid ${token.colorBorderSecondary}`,
            borderRadius: token.borderRadius,
          }}
        />
      ) : (
        <Empty description="无测试用例数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </div>
  )
}
