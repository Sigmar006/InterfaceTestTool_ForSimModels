import React, { useContext, useEffect } from 'react'
import {
  Drawer,
  Form,
  Input,
  Radio,
  InputNumber,
  Button,
  Space,
  Divider,
  Typography,
  message,
  Tooltip,
} from 'antd'
import {
  SettingOutlined,
  SaveOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import { AppContext } from '../context/AppContext'

const { Title, Text } = Typography

export default function Settings({ open, onClose }) {
  const { settings, updateSettings, currentRun } = useContext(AppContext)
  const [form] = Form.useForm()

  // Sync form when drawer opens or settings change
  useEffect(() => {
    if (open) {
      form.setFieldsValue(settings)
    }
  }, [open, settings, form])

  const handleSave = () => {
    form
      .validateFields()
      .then((values) => {
        updateSettings(values)
        message.success('设置已保存')
        onClose()
      })
      .catch(() => {
        // validation errors shown inline
      })
  }

  // Try to show cmake version info from last run env_check
  const cmakeVersionInfo = currentRun?.result?.env_check?.cmake_version || null

  return (
    <Drawer
      title={
        <Space>
          <SettingOutlined />
          <span>构建设置</span>
        </Space>
      }
      open={open}
      onClose={onClose}
      width={400}
      footer={
        <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>
            保存设置
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" initialValues={settings}>
        {/* CMake Path */}
        <Divider orientation="left" orientationMargin={0}>
          <Text style={{ fontSize: 13 }}>CMake</Text>
        </Divider>

        <Form.Item
          name="cmake_path"
          label={
            <Space>
              cmake 路径
              <Tooltip title="cmake 可执行文件的路径，或直接输入 cmake（如果已加入 PATH）">
                <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
              </Tooltip>
            </Space>
          }
          rules={[{ required: true, message: '请输入 cmake 路径' }]}
        >
          <Input
            placeholder="cmake"
            addonAfter={
              <Button
                type="text"
                size="small"
                style={{ height: 'auto', padding: '0 4px' }}
                onClick={() => {
                  // Placeholder: show info about cmake version from last run
                  if (cmakeVersionInfo) {
                    message.info(`检测到 cmake 版本: ${cmakeVersionInfo}`)
                  } else {
                    message.info('cmake 版本信息将在运行后显示')
                  }
                }}
              >
                检测
              </Button>
            }
          />
        </Form.Item>

        {cmakeVersionInfo && (
          <div
            style={{
              background: '#f6ffed',
              border: '1px solid #b7eb8f',
              borderRadius: 4,
              padding: '6px 10px',
              marginBottom: 12,
              fontSize: 12,
              color: '#389e0d',
            }}
          >
            cmake 版本: {cmakeVersionInfo}
          </div>
        )}

        {/* Build Type */}
        <Divider orientation="left" orientationMargin={0}>
          <Text style={{ fontSize: 13 }}>编译选项</Text>
        </Divider>

        <Form.Item name="build_type" label="编译类型">
          <Radio.Group buttonStyle="solid">
            <Radio.Button value="Debug">Debug</Radio.Button>
            <Radio.Button value="Release">Release</Radio.Button>
            <Radio.Button value="RelWithDebInfo">RelWithDebInfo</Radio.Button>
          </Radio.Group>
        </Form.Item>

        <Form.Item name="cpp_standard" label="C++ 标准">
          <Radio.Group buttonStyle="solid">
            <Radio.Button value="14">C++14</Radio.Button>
            <Radio.Button value="17">C++17</Radio.Button>
            <Radio.Button value="20">C++20</Radio.Button>
          </Radio.Group>
        </Form.Item>

        {/* Test Options */}
        <Divider orientation="left" orientationMargin={0}>
          <Text style={{ fontSize: 13 }}>测试选项</Text>
        </Divider>

        <Form.Item
          name="test_timeout"
          label="测试超时（秒）"
          rules={[
            { required: true, message: '请设置超时时间' },
            { type: 'number', min: 1, max: 3600, message: '范围 1-3600 秒' },
          ]}
        >
          <InputNumber
            min={1}
            max={3600}
            style={{ width: '100%' }}
            addonAfter="秒"
          />
        </Form.Item>

        {/* GTest */}
        <Divider orientation="left" orientationMargin={0}>
          <Text style={{ fontSize: 13 }}>Google Test</Text>
        </Divider>

        <Form.Item
          name="gtest_version"
          label={
            <Space>
              GTest 版本
              <Tooltip title="将通过 FetchContent 从 GitHub 下载指定版本的 GoogleTest">
                <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
              </Tooltip>
            </Space>
          }
        >
          <Input placeholder="1.14.0" />
        </Form.Item>
      </Form>
    </Drawer>
  )
}
