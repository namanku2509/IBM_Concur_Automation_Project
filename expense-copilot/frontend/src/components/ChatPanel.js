import React, { useEffect } from 'react';
import './ChatPanel.css';

// WXO loader is initialised in public/index.html.
// ChatPanel renders the header and the container div that wxoLoader targets
// via rootElementID: "wxo-chat-container".

function ChatPanel() {
  useEffect(() => {
    // index.html waits for this signal before initialising the loader. This
    // prevents it from mounting against a duplicate or not-yet-rendered node.
    window.dispatchEvent(new Event('wxo-chat-container-ready'));
  }, []);

  return (
    <div className="chat-panel">
      {/* wxoLoader mounts the agent UI inside this div */}
      <div id="wxo-chat-container" className="wxo-chat-container" />
    </div>
  );
}

export default ChatPanel;
