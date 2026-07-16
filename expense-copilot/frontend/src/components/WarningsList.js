import React from 'react';
import { InlineNotification } from '@carbon/react';

/**
 * Safely convert any warning value (string, object, Pydantic error) into
 * a renderable { code, message, severity } shape.
 */
function normaliseWarning(w, idx) {
  if (!w) return { code: `W${idx}`, message: 'Unknown warning', severity: 'WARNING' };

  // Already a proper object
  if (typeof w === 'object') {
    // Pydantic v2 error shape: { type, loc, msg, input, ctx }
    if (w.msg && !w.message) {
      const loc = Array.isArray(w.loc) ? w.loc.join(' → ') : '';
      return {
        code:     w.type  || `VALIDATION_ERROR_${idx}`,
        message:  loc ? `${loc}: ${w.msg}` : w.msg,
        severity: 'ERROR',
      };
    }
    return {
      code:     w.code     || `W${idx}`,
      message:  w.message  || w.msg || JSON.stringify(w),
      severity: w.severity || 'WARNING',
    };
  }

  // Plain string
  return { code: `W${idx}`, message: String(w), severity: 'WARNING' };
}

function WarningsList({ warnings }) {
  if (!warnings || warnings.length === 0) return null;

  const normalised = warnings.map(normaliseWarning);

  // Deduplicate by code
  const unique = normalised.filter(
    (w, i, arr) => arr.findIndex(x => x.code === w.code) === i
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      {unique.map((w, i) => (
        <InlineNotification
          key={w.code + i}
          kind={w.severity === 'ERROR' ? 'error' : 'warning'}
          title={String(w.code).replace(/_/g, ' ')}
          subtitle={String(w.message)}
          hideCloseButton
        />
      ))}
    </div>
  );
}

export default WarningsList;
