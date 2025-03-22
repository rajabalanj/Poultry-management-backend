import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import BatchManagement from './components/BatchManagement';
import AddBatch from './components/AddBatch';

const App = () => {
  return (
    <Router>
      <div className="flex">
        <Sidebar />
        <div className="flex-1 ml-64">
          <Routes>
            <Route path="/" element={<Navigate to="/batches" replace />} />
            <Route path="/batches" element={<BatchManagement />} />
            <Route path="/add-batch" element={<AddBatch />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
};

export default App; 