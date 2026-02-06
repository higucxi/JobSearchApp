import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'applications/json',
    },
});

export const searchJobs = async (params) => {
    const response = await api.get('/jobs/search', { params });
    return response.data;
};

export const getJobById = async (jobId) => {
    const response = await api.get(`/jobs/${jobId}`);
    return response.data;
};

export const getApplications = async () => {
    const response = await api.get('/applications');
    return response.data;
};

export const deleteApplication = async (jobId) => {
    const response = await api.delete(`/applications/${jobId}`);
    return response.data;
};

export const ingestJobs = async (data) => {
    const response = await api.post('/jobs/ingest', data);
    return response.data;
};

export default api;
