import React, { useState, useContext } from 'react'
import {
  Upload,
  Button,
  Tag,
  Typography,
  Space,
  message,
  Spin,
  Card,
  List,
} from 'antd'
import {
  InboxOutlined,
  FileOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import { AppContext } from '../context/AppContext'
import { createSession, uploadFiles } from '../api/session'
import { parseHeader } from '../api/parse'

const { Dragger } = Upload
const { Title, Text } = Typography

const ACCEPTED_EXTENSIONS = ['.dll', '.so', '.h', '.hpp']

function getFileType(filename) {
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase()
  if (ext === '.dll' || ext === '.so') return 'library'
  if (ext === '.h' || ext === '.hpp') return 'header'
  return 'unknown'
}

function getFileTypeColor(type) {
  if (type === 'library') return 'blue'
  if (type === 'header') return 'green'
  return 'default'
}

export default function FileUploader() {
  const {
    sessionId,
    setSessionId,
    setParseResult,
    setUploadedFiles,
    uploadedFiles,
    setStep,
  } = useContext(AppContext)

  const [fileList, setFileList] = useState([])
  const [uploading, setUploading] = useState(false)
  const [parsing, setParsing] = useState(false)
  const [parseError, setParseError] = useState(null)

  const handleUploadAndParse = async () => {
    if (fileList.length === 0) {
      message.warning('请先选择文件')
      return
    }

    // Check that there is at least one header file
    const hasHeader = fileList.some((f) => {
      const type = getFileType(f.name)
      return type === 'header'
    })
    if (!hasHeader) {
      message.warning('请至少上传一个头文件 (.h 或 .hpp)')
      return
    }

    setUploading(true)
    setParseError(null)

    try {
      // Create session if needed
      let sid = sessionId
      if (!sid) {
        const res = await createSession()
        sid = res.data.session_id
        setSessionId(sid)
      }

      // Build FormData
      const formData = new FormData()
      fileList.forEach((f) => {
        formData.append('files', f.originFileObj || f)
      })

      const uploadRes = await uploadFiles(sid, formData)
      const uploaded = uploadRes.data.files || []
      setUploadedFiles(uploaded)
      setUploading(false)

      // Auto-parse headers
      setParsing(true)
      const headerFiles = uploaded.filter((f) => f.type === 'header')
      if (headerFiles.length === 0) {
        message.error('未找到可解析的头文件')
        setParsing(false)
        return
      }

      const parsePayload = {
        header_files: headerFiles.map((f) => f.path || f.filename),
        compiler_args: ['-x', 'c++'],
      }

      const parseRes = await parseHeader(sid, parsePayload)
      setParseResult(parseRes.data)
      setStep(3)
      message.success('解析完成，共发现 ' + (parseRes.data.functions?.length || 0) + ' 个函数')
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || '操作失败'
      setParseError(errMsg)
      message.error('错误: ' + errMsg)
    } finally {
      setUploading(false)
      setParsing(false)
    }
  }

  const draggerProps = {
    name: 'file',
    multiple: true,
    fileList,
    beforeUpload: (file) => {
      const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
      if (!ACCEPTED_EXTENSIONS.includes(ext)) {
        message.error(`不支持的文件类型: ${file.name}`)
        return Upload.LIST_IGNORE
      }
      return false // prevent auto upload
    },
    onChange: (info) => {
      setFileList(info.fileList)
    },
    onRemove: (file) => {
      setFileList((prev) => prev.filter((f) => f.uid !== file.uid))
    },
    accept: ACCEPTED_EXTENSIONS.join(','),
    showUploadList: false,
  }

  const isLoading = uploading || parsing

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: 'calc(100vh - 96px)',
        padding: 32,
      }}
    >
      <Card
        style={{ width: '100%', maxWidth: 640 }}
        title={
          <Space>
            <InboxOutlined style={{ color: '#1677ff' }} />
            <span>上传测试文件</span>
          </Space>
        }
      >
        <Dragger {...draggerProps} style={{ marginBottom: 16 }}>
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持 .dll、.so（动态库）和 .h、.hpp（头文件）
          </p>
        </Dragger>

        {/* File list */}
        {fileList.length > 0 && (
          <List
            size="small"
            style={{ marginBottom: 16, maxHeight: 240, overflowY: 'auto' }}
            dataSource={fileList}
            renderItem={(file) => {
              const type = getFileType(file.name)
              return (
                <List.Item
                  style={{ padding: '4px 0' }}
                  actions={[
                    <Button
                      key="remove"
                      type="text"
                      size="small"
                      danger
                      onClick={() =>
                        setFileList((prev) => prev.filter((f) => f.uid !== file.uid))
                      }
                    >
                      移除
                    </Button>,
                  ]}
                >
                  <Space>
                    <FileOutlined />
                    <Text style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {file.name}
                    </Text>
                    <Tag color={getFileTypeColor(type)}>
                      {type === 'library' ? '动态库' : type === 'header' ? '头文件' : '未知'}
                    </Tag>
                  </Space>
                </List.Item>
              )
            }}
          />
        )}

        {/* Parse error */}
        {parseError && (
          <div
            style={{
              background: '#fff2f0',
              border: '1px solid #ffccc7',
              borderRadius: 6,
              padding: '8px 12px',
              marginBottom: 12,
              color: '#cf1322',
              fontSize: 13,
            }}
          >
            {parseError}
          </div>
        )}

        {/* Status message */}
        {isLoading && (
          <div style={{ textAlign: 'center', marginBottom: 12 }}>
            <Spin
              indicator={<LoadingOutlined />}
              tip={parsing ? '正在解析头文件...' : '正在上传文件...'}
            />
          </div>
        )}

        <Button
          type="primary"
          size="large"
          block
          onClick={handleUploadAndParse}
          disabled={fileList.length === 0 || isLoading}
          loading={isLoading}
          icon={isLoading ? undefined : <CheckCircleOutlined />}
        >
          {uploading ? '上传中...' : parsing ? '解析中...' : '上传并解析'}
        </Button>
      </Card>
    </div>
  )
}
