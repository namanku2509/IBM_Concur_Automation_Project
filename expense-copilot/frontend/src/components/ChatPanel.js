import { useEffect, useRef, useState } from 'react';
import './ChatPanel.css';

/**
 * ChatPanel — hosts the watsonx Orchestrate embedded chat widget.
 *
 * Lifecycle:
 *  1. Component mounts → container div (#wxo-chat-container) is in the DOM.
 *  2. We dispatch 'wxo-chat-container-ready' so the inline bootstrap script in
 *     index.html knows the div exists and can inject the WXO loader script.
 *  3. The index.html script sets window.wxoChatReady = true via the 'chat:ready'
 *     WXO SDK event once the widget iframe has fully loaded.
 *  4. After WXO_READY_TIMEOUT_MS we check if the widget is ready.  If not, we
 *     surface a human-readable "not configured" message so the UI is not blank.
 *
 * Notes:
 *  - The event must be dispatched AFTER the container div is mounted (useEffect
 *    with empty deps fires after the first render commit, so the div is present).
 *  - WXO_READY_TIMEOUT_MS is 12 s because the wxoLoader.js CDN fetch + widget
 *    bootstrap can take 8–10 s on the first load from a remote network.
 *  - The component accepts no props; chat state lives in the WXO widget itself.
 *    (ReportFolderPage previously passed `messages` / `onMessage` props here —
 *     those are forwarded to the BFF chat route, not to this component.)
 */

const WXO_READY_TIMEOUT_MS = 12000;

function ChatPanel() {
  const containerRef            = useRef(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    // Guard: only dispatch once the container div is confirmed in the DOM.
    // (useEffect fires after React commits the render, so containerRef.current
    //  is guaranteed to be set at this point.)
    if (!containerRef.current) return;

    // Signal to the bootstrap loader in index.html that the target div is ready.
    window.dispatchEvent(new Event('wxo-chat-container-ready'));

    // Start a fallback timer.  If the WXO widget hasn't signalled chat:ready
    // within the timeout, show the "not configured" notice instead of a blank panel.
    const timer = window.setTimeout(() => {
      if (!window.wxoChatReady) setUnavailable(true);
    }, WXO_READY_TIMEOUT_MS);

    return () => window.clearTimeout(timer);
  }, []); // run once after first mount

  return (
    <aside className="chat-panel" aria-label="watsonx Orchestrate travel and expense assistant">
      <div id="wxo-chat-container" ref={containerRef} className="wxo-chat-container" />
      {unavailable && (
        <div className="wxo-unavailable">
          watsonx Orchestrate is not configured. Add the WXO values and signing key to the BFF environment.
        </div>
      )}
    </aside>
  );
}

export default ChatPanel;
