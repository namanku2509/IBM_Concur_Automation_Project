function parseSelectedTxnIds(value) {
  if (!value) return null;

  if (Array.isArray(value)) return value;

  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : null;
    } catch (_) {
      return null;
    }
  }

  return null;
}

function getVisibleTransactions(transactions, folder, txnIdsParam) {
  const explicitIds = parseSelectedTxnIds(txnIdsParam);
  const storedIds = parseSelectedTxnIds(folder?.selectedTxnIds);
  const selectedTxnIds = explicitIds ?? storedIds ?? null;

  if (!selectedTxnIds || !Array.isArray(selectedTxnIds) || selectedTxnIds.length === 0) {
    return { transactions, selectedTxnIds: null };
  }

  const allowed = new Set(selectedTxnIds);
  const filtered = (transactions || []).filter(t => allowed.has(t.transactionId));
  return { transactions: filtered, selectedTxnIds };
}

module.exports = { getVisibleTransactions, parseSelectedTxnIds };
