import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import SearchPage from './pages/SearchPage';
import JobDetailPage from './pages/JobDetailPage';
import ApplicationsPage from './pages/ApplicationPage';

function Navigation() {
    const location = useLocation();

    const isActive = (path) => {
        return location.pathname == path ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300';
    };

    return (
        <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
            <div className="flex">
                <div className="flex-shrink-0 flex items-center">
                <h1 className="text-2xl font-bold text-gray-900">
                    Job Aggregator
                </h1>
                </div>
                <div className="hidden sm:ml-8 sm:flex sm:space-x-8">
                <Link
                    to="/"
                    className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${isActive('/')}`}
                >
                    Search Jobs
                </Link>
                <Link
                    to="/applications"
                    className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${isActive('/applications')}`}
                >
                    My Applications
                </Link>
                </div>
            </div>
            </div>
        </div>
        </nav>
    );
}

function App() {
    return (
        <Router>
        <div className="min-h-screen bg-gray-50">
            <Navigation />
            <main>
            <Routes>
                <Route path="/" element={<SearchPage />} />
                <Route path="/job/:jobId" element={<JobDetailPage />} />
                <Route path="/applications" element={<ApplicationsPage />} />
            </Routes>
            </main>
        </div>
        </Router>
    );
}

export default App;