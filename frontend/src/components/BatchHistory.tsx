import React, { useEffect, useState } from 'react';
import axios from 'axios';

interface HistoryRecord {
  id: number;
  batch_id: number;
  batch: string;
  action: string;
  changed_at: string;
  changed_by: string | null;
  previous_value: string | null;
  new_value: string | null;
  additional_info: string | null;
}

const BatchHistory = () => {
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('');

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await axios.get(`${import.meta.env.VITE_API_URL}/batch-history`);
        setHistory(response.data);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch history records');
        setLoading(false);
      }
    };

    fetchHistory();
  }, []);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatValue = (value: string | null) => {
    if (!value) return '';
    try {
      const parsed = JSON.parse(value);
      return Object.entries(parsed)
        .map(([key, val]) => `${key}: ${val}`)
        .join(', ');
    } catch {
      return value;
    }
  };

  const getActionColor = (action: string) => {
    switch (action) {
      case 'CREATE':
        return 'bg-green-100 text-green-800';
      case 'UPDATE':
        return 'bg-blue-100 text-blue-800';
      case 'DELETE':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const filteredHistory = history.filter(record => 
    !filter || record.action === filter
  );

  if (loading) return <div className="p-4">Loading...</div>;
  if (error) return <div className="p-4 text-red-600">{error}</div>;

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Batch History</h2>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="border rounded-lg px-3 py-2"
        >
          <option value="">All Actions</option>
          <option value="CREATE">Create</option>
          <option value="UPDATE">Update</option>
          <option value="DELETE">Delete</option>
        </select>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Batch
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Action
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Changed By
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Changed At
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Details
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredHistory.map((record) => (
              <tr key={record.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {record.batch}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getActionColor(record.action)}`}>
                    {record.action}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {record.changed_by || 'System'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatDate(record.changed_at)}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">
                  {record.action === 'UPDATE' ? (
                    <div>
                      <div className="text-xs text-gray-400">Previous:</div>
                      <div>{formatValue(record.previous_value)}</div>
                      <div className="text-xs text-gray-400 mt-1">New:</div>
                      <div>{formatValue(record.new_value)}</div>
                    </div>
                  ) : (
                    <div>{record.additional_info}</div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default BatchHistory; 