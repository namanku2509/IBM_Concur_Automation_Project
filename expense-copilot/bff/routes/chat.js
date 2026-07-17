/**
 * chat.js
 * -------
 * Serves the watsonx Orchestrate Chat Loader configuration to the frontend.
 * All credentials live in .env so they never appear in the React bundle.
 *
 * GET /api/chat/config
 *   Returns the full wxOConfiguration object the frontend needs to boot wxoLoader.
 *   Returns { configured: false } when env vars are missing so the panel degrades
 *   gracefully without breaking the rest of the app.
 */
const express = require('express');
const router  = express.Router();

router.get('/config', (req, res) => {
  const orchestrationID     = process.env.WXO_ORCHESTRATION_ID      || '';
  const hostURL             = process.env.WXO_HOST_URL               || '';
  const crn                 = process.env.WXO_CRN                    || '';
  const agentId             = process.env.WXO_AGENT_ID               || '';
  const agentEnvironmentId  = process.env.WXO_AGENT_ENVIRONMENT_ID   || '';

  if (!orchestrationID || !hostURL || !agentId) {
    return res.json({ configured: false });
  }

  res.json({
    configured: true,
    orchestrationID,
    hostURL,
    crn,
    deploymentPlatform: 'ibmcloud',
    chatOptions: {
      agentId,
      agentEnvironmentId,
    },
  });
});

module.exports = router;
