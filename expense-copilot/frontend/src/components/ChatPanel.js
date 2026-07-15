import React, { useState, useEffect, useRef } from 'react';
import './ChatPanel.css';

// ── Simple intent matcher ─────────────────────────────────────────────────────
// Recognises a small set of keywords and returns a canned agent response.
// This will be replaced by real watsonx Orchestrate API calls in a later phase.
function matchIntent(text) {
  const t = text.toLowerCase();
  if (t.match(/\b(status|state|progress)\b/))
    return 'Your report is currently being processed. Check the folder status badge at the top.';
  if (t.match(/\b(cancel|stop|quit|abort)\b/))
    return 'To cancel, click the Cancel button at the bottom of the report. Your data will not be saved.';
  if (t.match(/\b(help|how|what)\b/))
    return 'I can help you file your expenses. Upload your receipts and I will extract, match, and validate them automatically.';
  if (t.match(/\b(submit|send|done|finish)\b/))
    return 'Once your receipts are processed, click the Submit Report button at the bottom to send to SAP Concur.';
  if (t.match(/\b(warning|policy|limit)\b/))
    return 'Policy warnings do not block submission — they are informational. Errors (in red) must be resolved first.';
  if (t.match(/\b(match|transaction|card)\b/))
    return 'I automatically match your uploaded receipts to your corporate card transactions. Unmatched items are flagged for manual review.';
  return "I'm here to help you file your expenses. You can ask me about status, warnings, or how to submit.";
}

// ── ChatPanel component ───────────────────────────────────────────────────────
function ChatPanel({ messages, onMessage, folderStatus }) {
  const [input, setInput] = useState('');
  const bottomRef = useRef(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function handleSend() {
    const text = input.trim();
    if (!text) return;

    // Add employee message
    onMessage && onMessage({ from: 'user', text, ts: new Date().toLocaleTimeString() });
    setInput('');

    // Respond after short delay
    setTimeout(() => {
      const reply = matchIntent(text);
      onMessage && onMessage({ from: 'agent', text: reply, ts: new Date().toLocaleTimeString() });
    }, 400);
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  // Normalise — messages can be plain strings (from page) or objects (from here)
  const normalised = messages.map((m, i) =>
    typeof m === 'string'
      ? { from: 'agent', text: m, ts: '', id: i }
      : { ...m, id: i }
  );

  return (
    <div className="chat-panel">
      <div className="chat-panel-header">
        <p className="chat-panel-header-title">AI Expense Copilot</p>
        <p className="chat-panel-header-sub">Powered by watsonx Orchestrate</p>
      </div>

      <div className="chat-panel-messages">
        {normalised.map(msg => (
          <div key={msg.id} className={`chat-bubble chat-bubble--${msg.from}`}>
            {msg.text}
            {msg.ts && <span className="chat-bubble-time">{msg.ts}</span>}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <textarea
          className="chat-input"
          placeholder="Ask me anything…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={!input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default ChatPanel;
