import React from 'react'
import { Select } from 'antd'

/**
 * Select for enum types.
 * @param {object} props
 * @param {object} props.typeInfo - type object { kind, raw, values: string[] }
 * @param {string} props.value
 * @param {function} props.onChange
 * @param {boolean} props.disabled
 */
export default function EnumSelect({ typeInfo, value, onChange, disabled }) {
  const values = typeInfo?.values || []

  const options = values.map((v) => ({
    label: v,
    value: v,
  }))

  return (
    <Select
      value={value}
      onChange={onChange}
      disabled={disabled}
      options={options}
      style={{ width: '100%' }}
      placeholder={`选择 ${typeInfo?.raw || 'enum'} 值`}
      allowClear
      showSearch
      optionFilterProp="label"
    />
  )
}
