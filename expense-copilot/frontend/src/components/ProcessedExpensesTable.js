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
  { key: 'expenseType',      header: 'Type'     },
  { key: 'vendor',           header: 'Vendor'   },
  { key: 'amount',           header: 'Amount'   },
  { key: 'transactionDate',  header: 'Date'     },
  { key: 'matchStatus',      header: 'Match'    },
  { key: 'receiptFile',      header: 'Receipt'  },
];

function ProcessedExpensesTable({ expenses }) {
  if (!expenses || expenses.length === 0) return null;

  const rows = expenses.map((e, i) => ({
    id: e.expenseId || String(i),
    expenseType: e.expenseType,
    vendor: e.vendor,
    amount: `${e.currency} ${Number(e.amount).toLocaleString('en-IN')}`,
    transactionDate: e.transactionDate,
    matchStatus: e.matchedTxnId ? 'MATCHED' : 'UNMATCHED',
    receiptFile: e.receiptFileName || '—',
  }));

  return (
    <Tile style={{ padding: 0, overflow: 'hidden' }}>
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
                          type={cell.value === 'MATCHED' ? 'green' : 'red'}
                          size="sm"
                        >
                          {cell.value}
                        </Tag>
                      ) : cell.info.header === 'expenseType' ? (
                        <Tag type="blue" size="sm">{cell.value}</Tag>
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
