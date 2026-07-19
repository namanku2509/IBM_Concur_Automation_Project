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
} from '@carbon/react';

const HEADERS = [
  { key: 'expenseType',     header: 'Type'      },
  { key: 'vendor',         header: 'Vendor'    },
  { key: 'amount',         header: 'Amount'    },
  { key: 'transactionDate',header: 'Date'      },
  { key: 'matchStatus',    header: 'Match'     },
  { key: 'ocrStatus',      header: 'OCR'       },
  { key: 'actions',        header: ''          },
];

function ProcessedExpensesTable({ expenses, onRemove }) {
  if (!expenses || expenses.length === 0) return null;

  const rows = expenses.map((e, i) => {
    const hasAmount = e.amount && Number(e.amount) > 0;
    const hasVendor = e.vendor && e.vendor.trim();
    const ocrOk     = hasAmount && hasVendor;

    // Determine payment label:
    //   duplicate upload               → DUPLICATE
    //   matched to card txn            → CARD
    //   came from cash drop zone       → CASH
    //   card zone, no match found      → UNMATCHED
    const matchLabel = e.status === 'duplicate'
      ? 'DUPLICATE'
      : e.matchedTxnId
        ? 'CARD'
        : e.fromCashZone
          ? 'CASH'
          : 'UNMATCHED';

    return {
      id:              e.duplicateEntryId || e.expenseId || String(i),
      expenseType:     e.expenseType   || '—',
      vendor:          hasVendor ? e.vendor : '(not extracted)',
      amount:          hasAmount
        ? `${e.currency || 'INR'} ${Number(e.amount).toLocaleString('en-IN')}`
        : '₹ 0',
      transactionDate: e.transactionDate || '—',
      matchStatus:     matchLabel,
      ocrStatus:       ocrOk ? 'OK' : 'FAILED',
      actions:         e.id,
    };
  });

  return (
    <Tile className="processed-expenses-tile" style={{ padding: 0, overflow: 'hidden' }}>
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
                      {cell.info.header === 'matchStatus' ? (
                        <Tag
                          type={cell.value === 'CARD' ? 'green' : cell.value === 'CASH' ? 'teal' : cell.value === 'DUPLICATE' ? 'purple' : 'red'}
                          size="sm"
                        >
                          {cell.value}
                        </Tag>
                      ) : cell.info.header === 'ocrStatus' ? (
                        <Tag type={cell.value === 'OK' ? 'green' : 'magenta'} size="sm">
                          {cell.value === 'OK' ? 'OK' : 'OCR FAILED'}
                        </Tag>
                      ) : cell.info.header === 'expenseType' ? (
                        <Tag type="blue" size="sm">{cell.value}</Tag>
                      ) : cell.info.header === 'actions' ? (
                        <button
                          type="button"
                          className="processed-expenses-remove-button"
                          onClick={() => onRemove?.(row.id)}
                          aria-label="Remove uploaded receipt"
                        >
                          ×
                        </button>
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

export default ProcessedExpensesTable;
