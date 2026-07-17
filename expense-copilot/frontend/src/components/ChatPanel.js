import React from 'react';
import './ChatPanel.css';

// WXO loader is initialised in public/index.html.
// ChatPanel renders the header and the container div that wxoLoader targets
// via rootElementID: "wxo-chat-container".

function ChatPanel() {
  return (
    <div className="chat-panel">
      {/* wxoLoader mounts the agent UI inside this div */}
      <div id="wxo-chat-container" className="wxo-chat-container" />
    </div>
  );
}

export default ChatPanel;
