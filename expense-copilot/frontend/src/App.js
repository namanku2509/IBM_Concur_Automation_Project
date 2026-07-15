import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import CreateReportPage from './pages/CreateReportPage';
import ReportFolderPage from './pages/ReportFolderPage';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CreateReportPage />} />
        <Route path="/report/:reportId" element={<ReportFolderPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
