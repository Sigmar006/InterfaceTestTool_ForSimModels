import React, { useContext, useState, useEffect } from 'react'
import {
  Form,
  Button,
  Select,
  Switch,
  InputNumber,
  Input,
  Checkbox,
  Typography,
  Space,
  Divider,
  Empty,
  Alert,
  Tag,
  message,
  theme,
  Card,
  Row,
  Col,
} from 'antd'
import {
  PlayCircleOutlined,
  SaveOutlined,
  FunctionOutlined,
} from '@ant-design/icons'
import { AppContext } from '../../context/AppContext'
import { startRun } from '../../api/run'
import IntegerInput from './IntegerInput'
import PointerInput from './PointerInput'
import ArrayInput from './ArrayInput'
import StructInput from './StructInput'
import EnumSelect from './EnumSelect'

const { Title, Text } = Typography

const COMPARATORS = [
  { label: 'EXPECT_EQ (等于)', value: 'EXPECT_EQ' },
  { label: 'EXPECT_NE (不等于)', value: 'EXPECT_NE' },
  { label: 'EXPECT_GT (大于)', value: 'EXPECT_GT' },
  { label: 'EXPECT_LT (小于)', value: 'EXPECT_LT' },
  { label: 'EXPECT_GE (大于等于)', value: 'EXPECT_GE' },
  { label: 'EXPECT_LE (小于等于)', value: 'EXPECT_LE' },
  { label: 'EXPECT_NEAR (近似)', value: 'EXPECT_NEAR' },
]

/**
 * Renders the appropriate input component based on type kind.
 */
function TypeInput({ typeInfo, value, onChange, disabled }) {
  const kind = typeInfo?.kind || 'default'
  const raw = typeInfo?.raw || ''

  if (kind === 'integer') {
    return (
      <IntegerInput typeInfo={typeInfo} value={value} onChange={onChange} disabled={disabled} />
    )
  }
  if (kind === 'float') {
    return (
      <InputNumber
        value={value}
        onChange={onChange}
        disabled={disabled}
        step={0.001}
        style={{ width: '100%' }}
        addonAfter={<span style={{ color: '#8c8c8c', fontSize: 11 }}>{raw}</span>}
        placeholder="输入浮点数"
      />
    )
  }
  if (kind === 'bool') {
    return (
      <Switch
        checked={!!value}
        onChange={onChange}
        disabled={disabled}
        checkedChildren="true"
        unCheckedChildren="false"
      />
    )
  }
  if (kind === 'pointer' && raw.toLowerCase().includes('char')) {
    return (
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="输入字符串"
        style={{ width: '100%' }}
      />
    )
  }
  if (kind === 'pointer') {
    return (
      <PointerInput typeInfo={typeInfo} value={value} onChange={onChange} disabled={disabled} />
    )
  }
  if (kind === 'array') {
    return (
      <ArrayInput typeInfo={typeInfo} value={value} onChange={onChange} disabled={disabled} />
    )
  }
  if (kind === 'struct') {
    return (
      <StructInput typeInfo={typeInfo} value={value} onChange={onChange} disabled={disabled} />
    )
  }
  if (kind === 'enum') {
    return (
      <EnumSelect typeInfo={typeInfo} value={value} onChange={onChange} disabled={disabled} />
    )
  }
  if (kind === 'reference') {
    const inner = typeInfo?.pointee || typeInfo?.inner || { kind: 'default', raw: 'value' }
    return (
      <TypeInput typeInfo={inner} value={value} onChange={onChange} disabled={disabled} />
    )
  }
  // default: text input
  return (
    <Input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      placeholder={`输入 ${raw || kind}`}
      style={{ width: '100%' }}
    />
  )
}

function buildFunctionSignature(func) {
  if (!func) return ''
  const retType = func.return_type?.raw || 'void'
  const params = (func.params || [])
    .map((p) => `${p.type?.raw || p.type?.kind || 'auto'} ${p.name}`)
    .join(', ')
  return `${retType} ${func.name}(${params})`
}

function buildTestConfig(func, values) {
  const params = (func.params || []).map((p) => ({
    name: p.name,
    type: p.type,
    value: values.params?.[p.name],
    is_output: values.output_params?.includes(p.name) || false,
  }))

  const config = {
    function_name: func.name,
    params,
  }

  if (values.enable_expected) {
    config.expected_return = {
      comparator: values.expected_comparator || 'EXPECT_EQ',
      value: values.expected_value,
    }
  }

  return config
}

// Full single-function form
function SingleFunctionForm({ func }) {
  const {
    sessionId,
    parseResult,
    uploadedFiles,
    settings,
    setCurrentRun,
    addHistory,
    setStep,
  } = useContext(AppContext)
  const { token } = theme.useToken()

  const [form] = Form.useForm()
  const [enableExpected, setEnableExpected] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [savedCases, setSavedCases] = useState([])

  // Reset form when function changes
  useEffect(() => {
    form.resetFields()
    setEnableExpected(false)
  }, [func.name, form])

  const signature = buildFunctionSignature(func)
  const returnKind = func.return_type?.kind || 'void'
  const hasReturn = returnKind !== 'void'

  const handleRun = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)

      const testConfig = buildTestConfig(func, values)

      // Find library file
      const libFile = uploadedFiles.find(
        (f) => f.type === 'library' || f.filename?.match(/\.(dll|so)$/i)
      )
      const headerFile = uploadedFiles.find(
        (f) => f.type === 'header' || f.filename?.match(/\.(h|hpp)$/i)
      )

      const payload = {
        parse_id: parseResult?.parse_id,
        library_filename: libFile?.filename || libFile?.path || '',
        header_filename: headerFile?.filename || headerFile?.path || '',
        test_configs: [testConfig],
        options: {
          build_type: settings.build_type,
          cpp_standard: settings.cpp_standard,
          cmake_path: settings.cmake_path,
          test_timeout: settings.test_timeout,
          gtest_version: settings.gtest_version,
        },
      }

      const res = await startRun(sessionId, payload)
      const runId = res.data.run_id

      setCurrentRun({
        run_id: runId,
        status: 'running',
        logs: [],
        result: null,
      })
      setStep(4)
    } catch (err) {
      if (err?.errorFields) {
        // Validation error
        return
      }
      message.error('启动运行失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setSubmitting(false)
    }
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      const testConfig = buildTestConfig(func, values)
      setSavedCases((prev) => [...prev, testConfig])
      message.success('已保存为测试用例')
    } catch (err) {
      // validation error handled by form
    }
  }

  return (
    <div style={{ padding: 16 }}>
      {/* Function signature */}
      <div
        style={{
          background: token.colorFillTertiary,
          borderRadius: token.borderRadius,
          padding: '8px 12px',
          marginBottom: 16,
          fontFamily: 'monospace',
          fontSize: 13,
          color: token.colorTextSecondary,
          wordBreak: 'break-all',
        }}
      >
        <FunctionOutlined style={{ marginRight: 8, color: token.colorPrimary }} />
        {signature}
      </div>

      <Form
        form={form}
        layout="vertical"
        size="small"
        initialValues={{
          enable_expected: false,
          expected_comparator: 'EXPECT_EQ',
          output_params: [],
        }}
      >
        {/* Parameters */}
        {func.params && func.params.length > 0 && (
          <>
            <Divider orientation="left" orientationMargin={0} style={{ fontSize: 13 }}>
              参数
            </Divider>
            {func.params.map((param) => (
              <Form.Item
                key={param.name}
                name={['params', param.name]}
                label={
                  <Space>
                    <Text strong style={{ fontSize: 13 }}>{param.name}</Text>
                    <Tag style={{ fontSize: 11 }}>{param.type?.raw || param.type?.kind}</Tag>
                  </Space>
                }
              >
                <TypeInput typeInfo={param.type} />
              </Form.Item>
            ))}
          </>
        )}

        {/* Expected return */}
        {hasReturn && (
          <>
            <Divider orientation="left" orientationMargin={0} style={{ fontSize: 13 }}>
              期望返回值
            </Divider>
            <Form.Item name="enable_expected" valuePropName="checked">
              <Switch
                onChange={setEnableExpected}
                checkedChildren="启用"
                unCheckedChildren="跳过"
              />
            </Form.Item>

            {enableExpected && (
              <Row gutter={8}>
                <Col span={12}>
                  <Form.Item name="expected_comparator" label="比较方式">
                    <Select options={COMPARATORS} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="expected_value" label="期望值">
                    <TypeInput typeInfo={func.return_type} />
                  </Form.Item>
                </Col>
              </Row>
            )}
          </>
        )}

        {/* Output params */}
        {func.params && func.params.length > 0 && (
          <>
            <Divider orientation="left" orientationMargin={0} style={{ fontSize: 13 }}>
              输出参数
            </Divider>
            <Form.Item
              name="output_params"
              tooltip="勾选的参数将在测试输出中打印其值"
            >
              <Checkbox.Group style={{ width: '100%' }}>
                <Space wrap>
                  {func.params.map((param) => (
                    <Checkbox key={param.name} value={param.name}>
                      {param.name}
                    </Checkbox>
                  ))}
                </Space>
              </Checkbox.Group>
            </Form.Item>
          </>
        )}

        {/* Saved cases */}
        {savedCases.length > 0 && (
          <Alert
            type="info"
            message={`已保存 ${savedCases.length} 个测试用例`}
            style={{ marginBottom: 12 }}
          />
        )}

        {/* Action buttons */}
        <Divider style={{ margin: '12px 0' }} />
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button
            icon={<SaveOutlined />}
            onClick={handleSave}
            disabled={submitting}
          >
            保存为测试用例
          </Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleRun}
            loading={submitting}
          >
            ▶ 立即运行
          </Button>
        </Space>
      </Form>
    </div>
  )
}

// Bulk mode form (multiple functions selected)
function BulkForm({ funcs }) {
  const { sessionId, parseResult, uploadedFiles, settings, setCurrentRun, setStep } =
    useContext(AppContext)
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  const handleRun = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)

      const testConfigs = funcs.map((func) => {
        const config = { function_name: func.name, params: [] }
        if (values.enable_expected && func.return_type?.kind !== 'void') {
          config.expected_return = {
            comparator: values.expected_comparator || 'EXPECT_EQ',
            value: values.expected_value,
          }
        }
        return config
      })

      const libFile = uploadedFiles.find(
        (f) => f.type === 'library' || f.filename?.match(/\.(dll|so)$/i)
      )

      const payload = {
        parse_id: parseResult?.parse_id,
        library_filename: libFile?.filename || '',
        test_configs: testConfigs,
        options: {
          build_type: settings.build_type,
          cpp_standard: settings.cpp_standard,
          cmake_path: settings.cmake_path,
          test_timeout: settings.test_timeout,
        },
      }

      const res = await startRun(sessionId, payload)
      const runId = res.data.run_id
      setCurrentRun({ run_id: runId, status: 'running', logs: [], result: null })
      setStep(4)
    } catch (err) {
      if (err?.errorFields) return
      message.error('启动运行失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <Alert
        type="info"
        message={`批量模式：已选择 ${funcs.length} 个函数`}
        description="批量运行将使用默认参数值（零值），每个函数独立运行。"
        style={{ marginBottom: 16 }}
        showIcon
      />

      <Form form={form} layout="vertical" size="small">
        <Form.Item name="enable_expected" valuePropName="checked" label="启用返回值检查">
          <Switch checkedChildren="启用" unCheckedChildren="跳过" />
        </Form.Item>

        <Form.Item name="expected_comparator" label="比较方式">
          <Select options={COMPARATORS} defaultValue="EXPECT_EQ" />
        </Form.Item>

        <Form.Item name="expected_value" label="期望值">
          <Input placeholder="期望的返回值" />
        </Form.Item>

        <Divider />
        <div style={{ textAlign: 'right' }}>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleRun}
            loading={submitting}
          >
            ▶ 批量运行 ({funcs.length} 个函数)
          </Button>
        </div>
      </Form>
    </div>
  )
}

export default function ParamForm() {
  const { selectedFunctions } = useContext(AppContext)

  if (selectedFunctions.length === 0) {
    return (
      <div
        style={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <span>
              从左侧选择一个函数
              <br />
              <span style={{ fontSize: 12, color: '#8c8c8c' }}>
                按住 Ctrl 可多选
              </span>
            </span>
          }
        />
      </div>
    )
  }

  if (selectedFunctions.length === 1) {
    return <SingleFunctionForm func={selectedFunctions[0]} />
  }

  return <BulkForm funcs={selectedFunctions} />
}
