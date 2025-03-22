import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import UpdateBatchModal from './UpdateBatchModal';

interface Batch {
  id: number;
  shed_no: number;
  batch_no: string;
  age: string;
  opening_count: number;
  mortality: number;
  culls: number;
  closing_count: number;
  table: number;
  jumbo: number;
  cr: number;
  date: string;
}

const BatchManagement: React.FC = () => {
  const navigate = useNavigate();
  const [batches, setBatches] = useState<Batch[]>([]);
  const [error, setError] = useState<string>('');
  const [selectedBatch, setSelectedBatch] = useState<Batch | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const formatAge = (age: string): string => {
    const [week, day] = age.split('.');
    return `Week ${week}, Day ${day}`;
  };

  const calculateTotalEggs = (batch: Batch): number => {
    return batch.table + batch.jumbo + batch.cr;
  };

  const fetchBatches = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/batches/`);
      if (!response.ok) {
        throw new Error('Failed to fetch batches');
      }
      const data = await response.json();
      setBatches(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    }
  };

  useEffect(() => {
    fetchBatches();
  }, []);

  const handleRowClick = (batch: Batch) => {
    setSelectedBatch(batch);
    setIsModalOpen(true);
  };

  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Batch Management</h1>
        <button
          onClick={() => navigate('/add-batch')}
          className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
        >
          Add New Batch
        </button>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full bg-white border border-gray-300 shadow-sm rounded-lg">
          <thead>
            <tr className="bg-gray-50">
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Batch No.</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Shed No.</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Age</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Opening Count</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Mortality</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Culls</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Closing Count</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Table</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Jumbo</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">CR</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total Eggs</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr 
                key={batch.id} 
                className="hover:bg-gray-50 cursor-pointer"
                onClick={() => handleRowClick(batch)}
              >
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{batch.batch_no}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{batch.shed_no}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatAge(batch.age)}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{batch.opening_count}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{batch.mortality}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{batch.culls}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{batch.closing_count}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{batch.table}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{batch.jumbo}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{batch.cr}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-indigo-600">
                  {calculateTotalEggs(batch)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {new Date(batch.date).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedBatch && (
        <UpdateBatchModal
          batch={selectedBatch}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedBatch(null);
          }}
          onUpdate={fetchBatches}
        />
      )}
    </div>
  );
};

export default BatchManagement; 