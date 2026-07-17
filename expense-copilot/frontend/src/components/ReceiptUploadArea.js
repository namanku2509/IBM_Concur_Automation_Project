import React, { useRef } from 'react';
import { Tag, Loading } from '@carbon/react';
import { Upload } from '@carbon/icons-react';
import './ReceiptUploadArea.css';

function ReceiptUploadArea({ onUpload, processing, disabled, variant }) {
  const isCash = variant === 'cash';
  const inputRef = useRef(null);

  function handleFiles(files) {
    if (files && files.length > 0 && !processing) {
      onUpload(files);
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  }

  function handleDragOver(e) {
    e.preventDefault();
  }

  if (processing) {
    return (
      <div className={`upload-area upload-area--processing${isCash ? ' upload-area--cash' : ''}`}>
        <Loading small withOverlay={false} />
        <span>{isCash ? 'Processing cash receipts with AI…' : 'Processing your receipts with AI…'}</span>
      </div>
    );
  }

  return (
    <div
      className={`upload-area ${isCash ? 'upload-area--cash' : ''} ${disabled ? 'upload-area--disabled' : ''}`}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={disabled ? -1 : 0}
      onKeyDown={e => e.key === 'Enter' && !disabled && inputRef.current?.click()}
      aria-label="Upload receipts"
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept="application/pdf"
        style={{ display: 'none' }}
        onChange={e => handleFiles(e.target.files)}
      />
      <Upload size={32} className="upload-icon" />
      <p className="upload-title">{isCash ? 'Drop cash receipts here or click to upload' : 'Drop receipts here or click to upload'}</p>
      <p className="upload-hint">Accepted: PDF only</p>
      <div className="upload-tags">
        <Tag type={isCash ? 'teal' : 'blue'} size="sm">Multiple files supported</Tag>
        <Tag type={isCash ? 'teal' : 'blue'} size="sm">{isCash ? 'Added as out-of-pocket expense' : 'AI will extract and match automatically'}</Tag>
      </div>
    </div>
  );
}

export default ReceiptUploadArea;
