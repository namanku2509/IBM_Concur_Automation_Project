// Central config — swap these URLs to point at real Layer 2 and Layer 3
// without changing any other code
module.exports = {
  LAYER2_BASE_URL: process.env.LAYER2_BASE_URL || 'http://localhost:8000',
  LAYER3_BASE_URL: process.env.LAYER3_BASE_URL || 'http://localhost:8001',
};
