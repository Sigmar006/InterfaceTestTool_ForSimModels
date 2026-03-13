import React from 'react'
import { Collapse, InputNumber, Input, Switch, Select, Typography, theme } from 'antd'
import IntegerInput from './IntegerInput'
import PointerInput from './PointerInput'
import ArrayInput from './ArrayInput'
import EnumSelect from './EnumSelect'

const { Text } = Typography

/**
 * Renders struct fields as a collapsible set of inputs.
 * @param {object} props
 * @param {object} props.typeInfo - type object { kind, raw, fields: [{name, type}] }
 * @param {object} props.value - { fieldName: fieldValue, ... }
 * @param {function} props.onChange
 * @param {boolean} props.disabled
 * @param {number} props.depth - recursion depth to avoid infinite loops
 */
export default function StructInput({ typeInfo, value, onChange, disabled, depth = 0 }) {
  const { token } = theme.useToken()
  const fields = typeInfo?.fields || []
  const fieldValues = value || {}

  const handleFieldChange = (fieldName, fieldValue) => {
    onChange({ ...fieldValues, [fieldName]: fieldValue })
  }

  if (fields.length === 0) {
    return (
      <Input
        value={typeof value === 'string' ? value : JSON.stringify(value || {})}
        onChange={(e) => {
          try {
            onChange(JSON.parse(e.target.value))
          } catch {
            onChange(e.target.value)
          }
        }}
        disabled={disabled}
        placeholder={`输入 ${typeInfo?.raw || 'struct'} JSON`}
      />
    )
  }

  const items = fields.map((field) => ({
    key: field.name,
    label: (
      <span>
        <Text strong style={{ fontSize: 13 }}>{field.name}</Text>
        <Text style={{ fontSize: 11, color: token.colorTextTertiary, marginLeft: 8 }}>
          {field.type?.raw || field.type?.kind}
        </Text>
      </span>
    ),
    children: (
      <FieldInput
        typeInfo={field.type}
        value={fieldValues[field.name]}
        onChange={(val) => handleFieldChange(field.name, val)}
        disabled={disabled}
        depth={depth + 1}
      />
    ),
  }))

  return (
    <Collapse
      size="small"
      ghost
      style={{
        border: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: token.borderRadius,
      }}
      items={items}
    />
  )
}

// Recursive field renderer
function FieldInput({ typeInfo, value, onChange, disabled, depth }) {
  if (depth > 5) {
    return (
      <Input
        value={typeof value === 'string' ? value : JSON.stringify(value ?? '')}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="嵌套过深，请输入 JSON"
      />
    )
  }

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
      <StructInput
        typeInfo={typeInfo}
        value={value}
        onChange={onChange}
        disabled={disabled}
        depth={depth}
      />
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
      <FieldInput
        typeInfo={inner}
        value={value}
        onChange={onChange}
        disabled={disabled}
        depth={depth + 1}
      />
    )
  }
  return (
    <Input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      placeholder={`输入 ${raw || kind}`}
    />
  )
}
