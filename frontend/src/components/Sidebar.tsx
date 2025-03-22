import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const Sidebar = () => {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100';
  };

  return (
    <div className="w-64 h-screen bg-white border-r border-gray-200 fixed left-0 top-0">
      <div className="p-4">
        <h1 className="text-xl font-bold text-gray-800 mb-8">Poultry Management</h1>
        <nav className="space-y-2">
          <Link
            to="/batches"
            className={`flex items-center p-3 rounded-lg ${isActive('/batches')}`}
          >
            <svg 
              className="w-5 h-5 mr-3" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" 
              />
            </svg>
            Batch Management
          </Link>
        </nav>
      </div>
    </div>
  );
};

export default Sidebar; 