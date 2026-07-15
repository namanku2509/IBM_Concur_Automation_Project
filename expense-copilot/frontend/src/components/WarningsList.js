import React from 'react';
import { InlineNotification } from '@carbon/react';

function WarningsList({ warnings }) {
  if (!warnings || warnings.length === 0) return null;

  // Deduplicate by code
  const unique = warnings.filter(
    (w, i, arr) => arr.findIndex(x => x.code === w.code) === i
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      {unique.map(w => (
        <InlineNotification
          key={w.code}
          kind={w.severity === 'ERROR' ? 'error' : 'warning'}
          title={w.code.replace(/_/g, ' ')}
          subtitle={w.message}
          hideCloseButton
        />
      ))}
    </div>
  );
}

export default WarningsList;
