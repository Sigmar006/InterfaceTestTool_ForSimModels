import React from 'react'
import { Button, InputNumber, Input, Space, Typography } from 'antd'
import { PlusOutlined, MinusOutlined } from '@ant-design/icons'

const { Text } = Typography

/**
 * Dynamic list input for array types.
 * @param {object} props
 * @param {object} props.typeInfo - type object { kind, raw, element_type }
 * @param {Array} props.value - array of values
 * @param {function} props.onChange
 * @param {boolean} props.disabled
 */
export default function ArrayInput({ typeInfo, value, onChange, disabled }) {
  const items = Array.isArray(value) ? value : []
  const elementType = typeInfo?.element_type || { kind: 'default', raw: 'element' }
  const isNumeric =
    elementType.kind === 'integer' || elementType.kind === 'float'

  const handleAdd = () => {
    onChange([...items, isNumeric ? 0 : ''])
  }

  const handleRemove = (index) => {
    const next = items.filter((_, i) => i !== index)
    onChange(next)
  }

  const handleChange = (index, val) => {
    const next = [...items]
    next[index] = val
    onChange(next)
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Text style={{ fontSize: 12, color: '#8c8c8c' }}>
          {elementType.raw || elementType.kind}[]
        </Text>
        <Text style={{ fontSize: 12, color: '#8c8c8c' }}>({items.length} 项)</Text>
      </div>

      {items.map((item, index) => (
        <div
          key={index}
          style={{ display: 'flex', alignItems: 'center', gap: 8 }}
        >
          <Text style={{ fontSize: 12, color: '#8c8c8c', minWidth: 24 }}>
            [{index}]
          </Text>
          {isNumeric ? (
            <InputNumber
              value={item}
              onChange={(val) => handleChange(index, val)}
              disabled={disabled}
              precision={elementType.kind === 'float' ? undefined : 0}
              step={elementType.kind === 'float' ? 0.001 : 1}
              style={{ flex: 1 }}
            />
          ) : (
            <Input
              value={item}
              onChange={(e) => handleChange(index, e.target.value)}
              disabled={disabled}
              style={{ flex: 1 }}
              placeholder={`item[${index}]`}
            />
          )}
          <Button
            icon={<MinusOutlined />}
            size="small"
            danger
            onClick={() => handleRemove(index)}
            disabled={disabled}
          />
        </div>
      ))}

      <Button
        icon={<PlusOutlined />}
        size="small"
        onClick={handleAdd}
        disabled={disabled}
        type="dashed"
        style={{ width: '100%' }}
      >
        添加元素
      </Button>
    </Space>
  )
}
