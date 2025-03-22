import React, { useState } from 'react';

interface UpdateBatchModalProps {
  batch: {
    id: number;
    batch_no: string;
    mortality: number;
    culls: number;
    table: number;
    jumbo: number;
    cr: number;
  };
  isOpen: boolean;
  onClose: () => void;
  onUpdate: () => void;
}

const UpdateBatchModal: React.FC<UpdateBatchModalProps> = ({ batch, isOpen, onClose, onUpdate }) => {
  const [formData, setFormData] = useState({
    mortality: batch.mortality,
    culls: batch.culls,
    table: batch.table,
    jumbo: batch.jumbo,
    cr: batch.cr,
  });
  const [error, setError] = useState<string>('');

  const calculateTotalEggs = (): number => {
    return formData.table + formData.jumbo + formData.cr;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/batches/${batch.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          mortality: formData.mortality,
          culls: formData.culls,
          table: formData.table,
          jumbo: formData.jumbo,
          cr: formData.cr,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to update batch');
      }

      onUpdate();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Update Batch {batch.batch_no}</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Mortality</label>
            <input
              type="number"
              min="0"
              value={formData.mortality}
              onChange={(e) => setFormData(prev => ({ ...prev, mortality: parseInt(e.target.value) || 0 }))}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Culls</label>
            <input
              type="number"
              min="0"
              value={formData.culls}
              onChange={(e) => setFormData(prev => ({ ...prev, culls: parseInt(e.target.value) || 0 }))}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
              required
            />
          </div>

          <div className="border-t border-gray-200 pt-4 mt-4">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Egg Collection</h3>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Table</label>
                <input
                  type="number"
                  min="0"
                  value={formData.table}
                  onChange={(e) => setFormData(prev => ({ ...prev, table: parseInt(e.target.value) || 0 }))}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Jumbo</label>
                <input
                  type="number"
                  min="0"
                  value={formData.jumbo}
                  onChange={(e) => setFormData(prev => ({ ...prev, jumbo: parseInt(e.target.value) || 0 }))}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                  required
                />
              </div>

              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700">CR</label>
                <input
                  type="number"
                  min="0"
                  value={formData.cr}
                  onChange={(e) => setFormData(prev => ({ ...prev, cr: parseInt(e.target.value) || 0 }))}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                  required
                />
              </div>
            </div>

            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-gray-700">Total Eggs:</span>
                <span className="text-lg font-semibold text-indigo-600">{calculateTotalEggs()}</span>
              </div>
            </div>
          </div>

          <div className="flex justify-end space-x-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
            >
              Update
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UpdateBatchModal; 