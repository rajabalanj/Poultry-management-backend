import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface BatchFormData {
  shed_no: number;
  opening_count: number;
  age: string;
}

interface AgeError {
  week: string;
  day: string;
}

const AddBatch: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<BatchFormData>({
    shed_no: 1,
    opening_count: 0,
    age: '1.1'
  });

  const [week, setWeek] = useState('1');
  const [day, setDay] = useState('1');
  const [ageError, setAgeError] = useState<AgeError>({ week: '', day: '' });
  const [error, setError] = useState<string>('');

  const validateAge = (weekValue: string, dayValue: string): boolean => {
    const weekNum = parseInt(weekValue);
    const dayNum = parseInt(dayValue);
    let isValid = true;
    const newAgeError = { week: '', day: '' };

    if (weekNum < 1) {
      newAgeError.week = 'Week must be greater than 0';
      isValid = false;
    }
    if (dayNum < 1 || dayNum > 7) {
      newAgeError.day = 'Day must be between 1 and 7';
      isValid = false;
    }

    setAgeError(newAgeError);
    return isValid;
  };

  const handleAgeChange = (type: 'week' | 'day', value: string) => {
    if (type === 'week') {
      setWeek(value);
    } else {
      setDay(value);
    }

    if (validateAge(type === 'week' ? value : week, type === 'day' ? value : day)) {
      setFormData(prev => ({
        ...prev,
        age: `${type === 'week' ? value : week}.${type === 'day' ? value : day}`
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!validateAge(week, day)) {
      return;
    }

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/batches/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error('Failed to create batch');
      }

      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h2 className="text-2xl font-bold mb-4">Add New Batch</h2>
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Shed No.</label>
          <input
            type="number"
            min="1"
            value={formData.shed_no}
            onChange={(e) => setFormData(prev => ({ ...prev, shed_no: parseInt(e.target.value) }))}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Opening Count</label>
          <input
            type="number"
            min="0"
            value={formData.opening_count}
            onChange={(e) => setFormData(prev => ({ ...prev, opening_count: parseInt(e.target.value) }))}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Week</label>
            <input
              type="number"
              min="1"
              value={week}
              onChange={(e) => handleAgeChange('week', e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
              required
            />
            {ageError.week && <p className="text-red-500 text-sm mt-1">{ageError.week}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Day</label>
            <input
              type="number"
              min="1"
              max="7"
              value={day}
              onChange={(e) => handleAgeChange('day', e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
              required
            />
            {ageError.day && <p className="text-red-500 text-sm mt-1">{ageError.day}</p>}
          </div>
        </div>

        <div className="flex justify-end space-x-3">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
          >
            Add Batch
          </button>
        </div>
      </form>
    </div>
  );
};

export default AddBatch; 