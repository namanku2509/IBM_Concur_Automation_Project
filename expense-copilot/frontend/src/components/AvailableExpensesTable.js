import React from 'react';
import {
  DataTable,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  Tag,
  Tile,
  Loading,
  InlineNotification,
} from '@carbon/react';
import './AvailableExpensesTable.css';

const HEADERS = [
  { key: 'vendor',          header: 'Vendor'  },
  { key: 'amount',          header: 'Amount'  },
  { key: 'transactionDate', header: 'Date'    },
  { key: 'status',          header: 'Status'  },
];

function AvailableExpensesTable({ transactions, loading, error }) {
  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem 0' }}>
        <Loading small withOverlay={false} />
        <span style={{ fontSize: '0.875rem', color: '#525252' }}>
          Fetching your corporate card transactions…
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <InlineNotification
        kind="error"
        title="Failed to load transactions"
        subtitle={error}
        hideCloseButton
      />
    );
  }

  if (!transactions || transactions.length === 0) {
    return (
      <p style={{ fontSize: '0.875rem', color: '#525252', margin: 0 }}>
        No corporate card transactions found for this policy.
      </p>
    );
  }

  const rows = transactions.map(t => ({
    id: t.transactionId || t.txnId || String(Math.random()),
    vendor: t.vendor,
    amount: `${t.currency} ${Number(t.amount).toLocaleString('en-IN')}`,
    transactionDate: t.transactionDate || t.transaction_date,
    status: t.status,
  }));

  return (
    <Tile className="available-expenses-tile" style={{ padding: 0, overflow: 'hidden' }}>
      <DataTable rows={rows} headers={HEADERS} size="sm">
        {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
          <Table {...getTableProps()}>
            <TableHead>
              <TableRow>
                {headers.map(header => (
                  <TableHeader {...getHeaderProps({ header })} key={header.key}>
                    {header.header}
                  </TableHeader>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map(row => (
                <TableRow {...getRowProps({ row })} key={row.id}>
                  {row.cells.map(cell => (
                    <TableCell key={cell.id}>
                      {cell.info.header === 'status' ? (
                        <Tag
                          type={cell.value === 'MATCHED' ? 'green' : 'gray'}
                          size="sm"
                        >
                          {cell.value}
                        </Tag>
                      ) : cell.value}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DataTable>
    </Tile>
  );
}

export default AvailableExpensesTable;
