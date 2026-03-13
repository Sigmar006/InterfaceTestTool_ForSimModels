import React, { useState } from 'react'
import { Radio, Input, Space } from 'antd'

/**
 * Pointer input: radio to choose between passing a value or nullptr.
 * @param {object} props
 * @param {object} props.typeInfo - type object { kind, raw, pointee }
 * @param {*} props.value - { mode: 'value'|'nullptr', value: string }
 * @param {function} props.onChange
 * @param {boolean} props.disabled
 */
export default function PointerInput({ typeInfo, value, onChange, disabled }) {
  const mode = value?.mode ?? 'value'
  const inputValue = value?.value ?? ''

  const handleModeChange = (e) => {
    onChange({ mode: e.target.value, value: inputValue })
  }

  const handleValueChange = (e) => {
    onChange({ mode, value: e.target.value })
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Radio.Group
        value={mode}
        onChange={handleModeChange}
        disabled={disabled}
      >
        <Radio value="value">传值</Radio>
        <Radio value="nullptr">传 nullptr</Radio>
      </Radio.Group>
      {mode === 'value' && (
        <Input
          value={inputValue}
          onChange={handleValueChange}
          disabled={disabled}
          placeholder={`输入 ${typeInfo?.raw || 'pointer'} 值`}
          style={{ width: '100%' }}
        />
      )}
    </Space>
  )
}
