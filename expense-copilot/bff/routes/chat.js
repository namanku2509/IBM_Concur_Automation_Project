/**
 * Safely exposes the non-secret WXO configuration needed by the browser-side
 * chat widget loader (index.html bootstrap script).
 *
 * GET /api/chat/config
 *   Returns { configured: false } when WXO env vars are absent — the loader
 *   silently skips widget initialisation in that case.
 *
 *   Returns the full config object when all mandatory vars are present:
 *     orchestrationID       — WXO_ORCHESTRATION_ID
 *     hostURL               — WXO_HOST_URL  (e.g. https://us-south.assistant.watson.cloud.ibm.com)
 *     crn                   — WXO_CRN
 *     deploymentPlatform    — always 'ibmcloud'
 *     chatOptions.agentId   — WXO_AGENT_ID
 *     chatOptions.agentEnvironmentId — WXO_AGENT_ENVIRONMENT_ID (optional, omitted when blank)
 */
const express = require('express');
const router  = express.Router();

router.get('/config', (req, res) => {
  const orchestrationID    = process.env.WXO_ORCHESTRATION_ID    || '';
  const hostURL            = process.env.WXO_HOST_URL            || '';
  const crn                = process.env.WXO_CRN                 || '';
  const agentId            = process.env.WXO_AGENT_ID            || '';
  const agentEnvironmentId = process.env.WXO_AGENT_ENVIRONMENT_ID || '';

  // All three are mandatory for the widget to initialise.
  if (!orchestrationID || !hostURL || !agentId) {
    return res.json({ configured: false });
  }

  // chatOptions — only include agentEnvironmentId when it is actually set;
  // sending an empty string causes WXO SDK to throw a validation error.
  const chatOptions = { agentId };
  if (agentEnvironmentId) chatOptions.agentEnvironmentId = agentEnvironmentId;

  res.json({
    configured: true,
    orchestrationID,
    hostURL,
    crn,
    deploymentPlatform: 'ibmcloud',
    chatOptions,
  });
});

module.exports = router;
