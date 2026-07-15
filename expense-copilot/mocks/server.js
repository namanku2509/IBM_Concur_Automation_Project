const express = require('express');
const cors = require('cors');

const layer2 = require('./layer2');
const layer3 = require('./layer3');

const app = express();
app.use(cors());
app.use(express.json());

// Mount Layer 2 and Layer 3 mock routers on separate ports via sub-paths
// Layer 3 mock: /l3
// Layer 2 mock: /l2
app.use('/l3', layer3);
app.use('/l2', layer2);

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`Mock server running on http://localhost:${PORT}`);
  console.log(`  Layer 3 (Concur Stub mock) → http://localhost:${PORT}/l3`);
  console.log(`  Layer 2 (AI Middleware mock) → http://localhost:${PORT}/l2`);
});
