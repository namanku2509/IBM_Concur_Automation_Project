import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the expense claim workspace', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: /good morning/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /create expense report/i })).toBeInTheDocument();
});
