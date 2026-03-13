import React from 'react'
import { InputNumber } from 'antd'

/**
 * Integer input for int, long, short, char (numeric), etc.
 * @param {object} props
 * @param {object} props.typeInfo - type object from API { kind, raw }
 * @param {*} props.value
 * @param {function} props.onChange
 * @param {boolean} props.disabled
 */
export default function IntegerInput({ typeInfo, value, onChange, disabled }) {
  const raw = typeInfo?.raw || 'int'

  return (
    <InputNumber
      value={value}
      onChange={onChange}
      disabled={disabled}
      precision={0}
      style={{ width: '100%' }}
      addonAfter={<span style={{ color: '#8c8c8c', fontSize: 11 }}>{raw}</span>}
      placeholder="输入整数"
    />
  )
}
