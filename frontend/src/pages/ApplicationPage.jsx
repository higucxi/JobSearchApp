import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getApplications, deleteApplication } from '../services/api';

export default function ApplicationPage() {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('All');

  useEffect(() => {
    loadApplications();
  }, []);

  const loadApplications = async () => {
    try {
      const data = await getApplications();
      setApplications(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load applications');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (jobId) => {
    if (!confirm('Are you sure you want to remove this application from tracking?')) {
      return;
    }
    
    try {
      await deleteApplication(jobId);
      await loadApplications();
    } catch (err) {
      alert('Failed to delete application: ' + (err.response?.data?.detail || err.message));
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const getStatusColour = (status) => {
    const colors = {
      'Applied': 'bg-blue-100 text-blue-800 border-blue-200',
      'Interview': 'bg-yellow-100 text-yellow-800 border-yellow-200',
      'Offer': 'bg-green-100 text-green-800 border-green-200',
      'Rejected': 'bg-red-100 text-red-800 border-red-200',
      'Not Applied': 'bg-gray-100 text-gray-800 border-gray-200'
    };
    return colors[status] || colors['Not Applied'];
  };

  const statuses = ['All', 'Not Applied', 'Applied', 'Interview', 'Offer', 'Rejected'];
  
  const filteredApplications = filter === 'All' 
    ? applications 
    : applications.filter(app => app.status === filter);

  const getStatusCount = (status) => {
    if (status === 'All') return applications.length;
    return applications.filter(app => app.status === status).length;
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="text-center">Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">My Applications</h1>
        <p className="text-gray-600">Track and manage your job applications</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {/* Status Filter Tabs */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
        <div className="flex flex-wrap gap-2">
          {statuses.map((status) => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`px-4 py-2 rounded-md transition-colors ${
                filter === status
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {status} ({getStatusCount(status)})
            </button>
          ))}
        </div>
      </div>

      {/* Applications Grid */}
      {filteredApplications.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow-sm">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No applications</h3>
          <p className="mt-1 text-sm text-gray-500">
            {filter === 'All' 
              ? 'Start tracking applications from the search page'
              : `No applications with status "${filter}"`
            }
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredApplications.map((app) => (
            <div key={app.job_id} className={`bg-white rounded-lg shadow-sm border-2 ${getStatusColour(app.status)} hover:shadow-md transition-shadow`}>
              <div className="p-6">
                <div className="flex justify-between items-start mb-3">
                  <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColour(app.status)}`}>
                    {app.status}
                  </span>
                  <button
                    onClick={() => handleDelete(app.job_id)}
                    className="text-gray-400 hover:text-red-600"
                    title="Remove from tracking"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
                
                <Link to={`/job/${app.job_id}`} className="block mb-3">
                  <h3 className="text-lg font-semibold text-gray-900 hover:text-blue-600 mb-1">
                    {app.job.title}
                  </h3>
                  <p className="text-gray-600">{app.job.company}</p>
                </Link>
                
                <div className="text-sm text-gray-500 mb-3">
                  <div className="flex items-center mb-1">
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    {app.job.location}
                  </div>
                  <div className="flex items-center">
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Updated: {formatDate(app.updated_at)}
                  </div>
                </div>
                
                {app.notes && (
                  <div className="border-t pt-3">
                    <p className="text-sm text-gray-600 line-clamp-2">{app.notes}</p>
                  </div>
                )}
                
                <div className="flex flex-wrap gap-1 mt-3">
                  {app.job.sources.map((source, idx) => (
                    <span key={idx} className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded">
                      {source.source}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Summary Stats */}
      {applications.length > 0 && (
        <div className="mt-8 bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Application Summary</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {statuses.filter(s => s !== 'All').map((status) => {
              const count = getStatusCount(status);
              const percentage = applications.length > 0 
                ? Math.round((count / applications.length) * 100) 
                : 0;
              
              return (
                <div key={status} className="text-center">
                  <div className="text-2xl font-bold text-gray-900">{count}</div>
                  <div className="text-sm text-gray-600">{status}</div>
                  <div className="text-xs text-gray-500">{percentage}%</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}