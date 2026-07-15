import React, { useRef } from 'react';
import { Tag, Loading } from '@carbon/react';
import { Upload } from '@carbon/icons-react';
import './ReceiptUploadArea.css';

function ReceiptUploadArea({ onUpload, processing, disabled }) {
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
      <div className="upload-area upload-area--processing">
        <Loading small withOverlay={false} />
        <span>Processing your receipts with AI…</span>
      </div>
    );
  }

  return (
    <div
      className={`upload-area ${disabled ? 'upload-area--disabled' : ''}`}
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
      <p className="upload-title">Drop receipts here or click to upload</p>
      <p className="upload-hint">Accepted: PDF only</p>
      <div className="upload-tags">
        <Tag type="blue" size="sm">Multiple files supported</Tag>
        <Tag type="blue" size="sm">AI will extract and match automatically</Tag>
      </div>
    </div>
  );
}

export default ReceiptUploadArea;
