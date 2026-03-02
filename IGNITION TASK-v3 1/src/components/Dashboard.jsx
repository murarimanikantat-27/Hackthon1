import React, { useState, useEffect } from 'react';
import { PieChart, Pie, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import Sidebar from './Sidebar';
import IncidentModal from './IncidentModal';
import Header from './Header';
import Footer from './Footer';
import { API_ENDPOINTS } from '../config';

const Dashboard = ({ data, onBack, isDark, onThemeToggle }) => {
  const [activeTab, setActiveTab] = useState('failed');
  const [severityFilter, setSeverityFilter] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [isIncidentModalOpen, setIsIncidentModalOpen] = useState(false);
  
  if (!data) return null;

  const isTerraformFormat = data.check_type === 'terraform' && data.results;
  
  const getSeverityColor = (severity) => {
    const colors = {
      critical: 'bg-red-500',
      high: 'bg-orange-500',
      medium: 'bg-yellow-500',
      low: 'bg-blue-500',
      info: 'bg-slate-500'
    };
    return colors[severity?.toLowerCase()] || 'bg-slate-500';
  };

  const getStatusColor = (status) => {
    return status === 'PASSED' 
      ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400'
      : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400';
  };

  const getSeverityCountTerraform = (severity) => {
    if (!isTerraformFormat) return 0;
    return data.results.failed_checks?.filter(c => c.severity?.toLowerCase() === severity.toLowerCase()).length || 0;
  };

  const getSeverityCount = (severity) => {
    return data.vulnerabilities?.filter(v => v.severity?.toLowerCase() === severity.toLowerCase()).length || 0;
  };

  const totalChecks = isTerraformFormat 
    ? (data.results.failed_checks?.length || 0) + (data.results.passed_checks?.length || 0)
    : data.vulnerabilities?.length || 0;

  const failedCount = isTerraformFormat 
    ? data.results.failed_checks?.length || 0
    : data.vulnerabilities?.length || 0;

  const passedCount = isTerraformFormat 
    ? data.results.passed_checks?.length || 0
    : 0;

  let currentData = isTerraformFormat 
    ? (activeTab === 'failed' ? data.results.failed_checks : data.results.passed_checks)
    : data.vulnerabilities;

  if (severityFilter) {
    currentData = currentData?.filter(item => 
      item.severity?.toLowerCase() === severityFilter.toLowerCase()
    );
  }

  // Pagination logic
  const totalItems = currentData?.length || 0;
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedData = currentData?.slice(startIndex, endIndex);

  const handleCardClick = (severity) => {
    if (severityFilter === severity) {
      setSeverityFilter(null);
    } else {
      setSeverityFilter(severity);
      if (isTerraformFormat) {
        setActiveTab('failed');
      }
    }
    setCurrentPage(1); // Reset to first page when filtering
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSeverityFilter(null);
    setCurrentPage(1); // Reset to first page when changing tabs
  };

  const handleItemsPerPageChange = (value) => {
    setItemsPerPage(value);
    setCurrentPage(1); // Reset to first page when changing items per page
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
  };

  const getPageNumbers = () => {
    const pages = [];
    const maxVisible = 5;
    
    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      if (currentPage <= 3) {
        for (let i = 1; i <= 4; i++) pages.push(i);
        pages.push('...');
        pages.push(totalPages);
      } else if (currentPage >= totalPages - 2) {
        pages.push(1);
        pages.push('...');
        for (let i = totalPages - 3; i <= totalPages; i++) pages.push(i);
      } else {
        pages.push(1);
        pages.push('...');
        pages.push(currentPage - 1);
        pages.push(currentPage);
        pages.push(currentPage + 1);
        pages.push('...');
        pages.push(totalPages);
      }
    }
    
    return pages;
  };

  if (isIncidentModalOpen) {
    return (
      <IncidentModal 
        isOpen={isIncidentModalOpen} 
        onClose={() => setIsIncidentModalOpen(false)}
        isDark={isDark}
        onThemeToggle={onThemeToggle}
      />
    );
  }

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark flex flex-col overflow-x-hidden pt-16">
      <Header onThemeToggle={onThemeToggle} isDark={isDark} />
      <div className="flex-1 py-8 overflow-x-hidden">
        <Sidebar 
          onIncidentClick={() => setIsIncidentModalOpen(true)} 
          onVulnerabilitiesClick={() => {}}
          activeItem="vulnerabilities"
        />
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 ml-64 transition-all duration-300">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-navy-deep dark:text-white mb-2">
              Threat & Vulnerability Management Dashboard
            </h1>
            <div className="flex items-center gap-4 text-slate-500 dark:text-slate-400">
              <p>Scan Date: {data.scanDate || new Date().toLocaleDateString()}</p>
              {data.projectName && <p>• Project: {data.projectName}</p>}
              {isTerraformFormat && <p>• Type: {data.check_type}</p>}
            </div>
          </div>
          <button 
            onClick={onBack}
            className="flex items-center gap-2 px-4 py-2 bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg hover:opacity-80 transition-all"
          >
            <span className="material-symbols-outlined">arrow_back</span>
            Back to Upload
          </button>
        </div>

        {severityFilter && (
          <div className="mb-4 flex items-center gap-2 bg-primary/10 dark:bg-primary/20 px-4 py-2 rounded-lg">
            <span className="text-sm font-medium text-primary">Filtered by: {severityFilter.toUpperCase()}</span>
            <button 
              onClick={() => setSeverityFilter(null)}
              className="ml-auto text-primary hover:text-primary/80"
            >
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          </div>
        )}

        {isTerraformFormat ? (
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-8">
            <div className="bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mb-1">Total Checks</p>
                  <p className="text-3xl font-bold text-navy-deep dark:text-white">{totalChecks}</p>
                </div>
                <div className="w-12 h-12 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-slate-600 dark:text-slate-400">checklist</span>
                </div>
              </div>
            </div>

            <button 
              onClick={() => handleTabChange('failed')}
              className="bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-red-200 dark:border-red-900 hover:shadow-xl transition-all cursor-pointer text-left"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-red-600 dark:text-red-400 mb-1">Failed</p>
                  <p className="text-3xl font-bold text-red-600 dark:text-red-400">{failedCount}</p>
                </div>
                <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-red-600 dark:text-red-400">cancel</span>
                </div>
              </div>
            </button>

            <button 
              onClick={() => handleTabChange('passed')}
              className="bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-green-200 dark:border-green-900 hover:shadow-xl transition-all cursor-pointer text-left"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-green-600 dark:text-green-400 mb-1">Passed</p>
                  <p className="text-3xl font-bold text-green-600 dark:text-green-400">{passedCount}</p>
                </div>
                <div className="w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-green-600 dark:text-green-400">check_circle</span>
                </div>
              </div>
            </button>

            <button 
              onClick={() => handleCardClick('critical')}
              className={`bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-red-200 dark:border-red-900 hover:shadow-xl transition-all cursor-pointer text-left ${severityFilter === 'critical' ? 'ring-2 ring-red-500' : ''}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-red-600 dark:text-red-400 mb-1">Critical</p>
                  <p className="text-3xl font-bold text-red-600 dark:text-red-400">{getSeverityCountTerraform('critical')}</p>
                </div>
              </div>
            </button>

            <button 
              onClick={() => handleCardClick('high')}
              className={`bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-orange-200 dark:border-orange-900 hover:shadow-xl transition-all cursor-pointer text-left ${severityFilter === 'high' ? 'ring-2 ring-orange-500' : ''}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-orange-600 dark:text-orange-400 mb-1">High</p>
                  <p className="text-3xl font-bold text-orange-600 dark:text-orange-400">{getSeverityCountTerraform('high')}</p>
                </div>
              </div>
            </button>

            <button 
              onClick={() => handleCardClick('medium')}
              className={`bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-yellow-200 dark:border-yellow-900 hover:shadow-xl transition-all cursor-pointer text-left ${severityFilter === 'medium' ? 'ring-2 ring-yellow-500' : ''}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-yellow-600 dark:text-yellow-400 mb-1">Medium</p>
                  <p className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">{getSeverityCountTerraform('medium')}</p>
                </div>
              </div>
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
            <div className="bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mb-1">Total</p>
                  <p className="text-3xl font-bold text-navy-deep dark:text-white">{totalChecks}</p>
                </div>
                <div className="w-12 h-12 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-slate-600 dark:text-slate-400">bug_report</span>
                </div>
              </div>
            </div>

            <button 
              onClick={() => handleCardClick('critical')}
              className={`bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-red-200 dark:border-red-900 hover:shadow-xl transition-all cursor-pointer text-left ${severityFilter === 'critical' ? 'ring-2 ring-red-500' : ''}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-red-600 dark:text-red-400 mb-1">Critical</p>
                  <p className="text-3xl font-bold text-red-600 dark:text-red-400">{getSeverityCount('critical')}</p>
                </div>
                <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-red-600 dark:text-red-400">error</span>
                </div>
              </div>
            </button>

            <button 
              onClick={() => handleCardClick('high')}
              className={`bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-orange-200 dark:border-orange-900 hover:shadow-xl transition-all cursor-pointer text-left ${severityFilter === 'high' ? 'ring-2 ring-orange-500' : ''}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-orange-600 dark:text-orange-400 mb-1">High</p>
                  <p className="text-3xl font-bold text-orange-600 dark:text-orange-400">{getSeverityCount('high')}</p>
                </div>
                <div className="w-12 h-12 bg-orange-100 dark:bg-orange-900/30 rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-orange-600 dark:text-orange-400">warning</span>
                </div>
              </div>
            </button>

            <button 
              onClick={() => handleCardClick('medium')}
              className={`bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-yellow-200 dark:border-yellow-900 hover:shadow-xl transition-all cursor-pointer text-left ${severityFilter === 'medium' ? 'ring-2 ring-yellow-500' : ''}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-yellow-600 dark:text-yellow-400 mb-1">Medium</p>
                  <p className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">{getSeverityCount('medium')}</p>
                </div>
                <div className="w-12 h-12 bg-yellow-100 dark:bg-yellow-900/30 rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-yellow-600 dark:text-yellow-400">info</span>
                </div>
              </div>
            </button>

            <button 
              onClick={() => handleCardClick('low')}
              className={`bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-blue-200 dark:border-blue-900 hover:shadow-xl transition-all cursor-pointer text-left ${severityFilter === 'low' ? 'ring-2 ring-blue-500' : ''}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-blue-600 dark:text-blue-400 mb-1">Low</p>
                  <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">{getSeverityCount('low')}</p>
                </div>
                <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-blue-600 dark:text-blue-400">check_circle</span>
                </div>
              </div>
            </button>
          </div>
        )}

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Success vs Failure Pie Chart */}
          <div className="bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-slate-200 dark:border-slate-800">
            <h3 className="text-lg font-bold text-navy-deep dark:text-white mb-4">
              {isTerraformFormat ? 'Pass/Fail Status' : 'Security Status'}
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={isTerraformFormat ? [
                    { name: 'Passed', value: passedCount, color: '#22c55e' },
                    { name: 'Failed', value: failedCount, color: '#ef4444' }
                  ].filter(item => item.value > 0) : [
                    { name: 'Secure', value: totalChecks - failedCount, color: '#22c55e' },
                    { name: 'Vulnerable', value: failedCount, color: '#ef4444' }
                  ].filter(item => item.value > 0)}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent, value }) => `${name}: ${value} (${(percent * 100).toFixed(1)}%)`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {(isTerraformFormat ? [
                    { name: 'Passed', value: passedCount, color: '#22c55e' },
                    { name: 'Failed', value: failedCount, color: '#ef4444' }
                  ] : [
                    { name: 'Secure', value: totalChecks - failedCount, color: '#22c55e' },
                    { name: 'Vulnerable', value: failedCount, color: '#ef4444' }
                  ]).filter(item => item.value > 0).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1e293b', 
                    border: 'none', 
                    borderRadius: '8px',
                    color: '#fff'
                  }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Status Bar Chart */}
          <div className="bg-white dark:bg-slate-900 rounded-xl p-6 shadow-lg border border-slate-200 dark:border-slate-800">
            <h3 className="text-lg font-bold text-navy-deep dark:text-white mb-4">
              {isTerraformFormat ? 'Check Status Overview' : 'Severity Breakdown'}
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={isTerraformFormat ? [
                  { name: 'Failed', count: failedCount, color: '#ef4444' },
                  { name: 'Passed', count: passedCount, color: '#22c55e' }
                ] : [
                  { name: 'Critical', count: getSeverityCount('critical'), color: '#ef4444' },
                  { name: 'High', count: getSeverityCount('high'), color: '#f97316' },
                  { name: 'Medium', count: getSeverityCount('medium'), color: '#eab308' },
                  { name: 'Low', count: getSeverityCount('low'), color: '#3b82f6' }
                ]}
                margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" stroke="#64748b" />
                <YAxis stroke="#64748b" />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1e293b', 
                    border: 'none', 
                    borderRadius: '8px',
                    color: '#fff'
                  }}
                />
                <Legend />
                <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                  {(isTerraformFormat ? [
                    { name: 'Failed', count: failedCount, color: '#ef4444' },
                    { name: 'Passed', count: passedCount, color: '#22c55e' }
                  ] : [
                    { name: 'Critical', count: getSeverityCount('critical'), color: '#ef4444' },
                    { name: 'High', count: getSeverityCount('high'), color: '#f97316' },
                    { name: 'Medium', count: getSeverityCount('medium'), color: '#eab308' },
                    { name: 'Low', count: getSeverityCount('low'), color: '#3b82f6' }
                  ]).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {isTerraformFormat && (
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => handleTabChange('failed')}
              className={`px-6 py-3 rounded-lg font-semibold transition-all ${
                activeTab === 'failed'
                  ? 'bg-red-500 text-white'
                  : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800'
              }`}
            >
              Failed Checks ({failedCount})
            </button>
            <button
              onClick={() => handleTabChange('passed')}
              className={`px-6 py-3 rounded-lg font-semibold transition-all ${
                activeTab === 'passed'
                  ? 'bg-green-500 text-white'
                  : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800'
              }`}
            >
              Passed Checks ({passedCount})
            </button>
          </div>
        )}

        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-800 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
            <h2 className="text-xl font-bold text-navy-deep dark:text-white">
              {isTerraformFormat ? 'Security Check Details' : 'Vulnerability Details'}
              {currentData && <span className="text-sm font-normal text-slate-500 ml-2">({totalItems} items)</span>}
            </h2>
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-600 dark:text-slate-400">Show:</span>
              <select 
                value={itemsPerPage}
                onChange={(e) => handleItemsPerPageChange(Number(e.target.value))}
                className="px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={75}>75</option>
                <option value={100}>100</option>
              </select>
              <span className="text-sm text-slate-600 dark:text-slate-400">per page</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            {isTerraformFormat ? (
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-800">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Severity</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Check ID</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Check Name</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Resource</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">File</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Guideline</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {paginatedData?.map((check, index) => (
                    <tr key={index} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${getStatusColor(check.check_result?.result)}`}>
                          {check.check_result?.result || 'UNKNOWN'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold text-white ${getSeverityColor(check.severity)}`}>
                          {check.severity || 'N/A'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-slate-900 dark:text-slate-100">
                        {check.check_id || 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-900 dark:text-slate-100 max-w-md">
                        {check.check_name || 'No description'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900 dark:text-slate-100">
                        {check.resource || 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">
                        {check.file_path || 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {check.guideline ? (
                          <a 
                            href={check.guideline} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-primary hover:underline flex items-center gap-1"
                          >
                            <span className="material-symbols-outlined text-sm">open_in_new</span>
                            View
                          </a>
                        ) : (
                          <span className="text-slate-400">N/A</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-800">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Severity</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">ID</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Title</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Package</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Version</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {paginatedData?.map((vuln, index) => (
                    <tr key={index} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold text-white ${getSeverityColor(vuln.severity)}`}>
                          {vuln.severity || 'Unknown'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-slate-900 dark:text-slate-100">
                        {vuln.id || vuln.cve || 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-900 dark:text-slate-100 max-w-md">
                        {vuln.title || vuln.description || 'No description'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900 dark:text-slate-100">
                        {vuln.package || vuln.packageName || 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">
                        {vuln.version || vuln.installedVersion || 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          vuln.status === 'fixed' || vuln.fixAvailable 
                            ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400' 
                            : 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-400'
                        }`}>
                          {vuln.status || (vuln.fixAvailable ? 'Fix Available' : 'Open')}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="mt-6 flex flex-col sm:flex-row justify-between items-center gap-4 bg-white dark:bg-slate-900 rounded-xl p-4 shadow-lg border border-slate-200 dark:border-slate-800">
            <div className="text-sm text-slate-600 dark:text-slate-400">
              Showing {startIndex + 1} to {Math.min(endIndex, totalItems)} of {totalItems} items
            </div>
            
            <div className="flex items-center gap-2">
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                className="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                <span className="material-symbols-outlined text-sm">chevron_left</span>
              </button>
              
              <div className="flex gap-1">
                {getPageNumbers().map((page, index) => (
                  page === '...' ? (
                    <span key={`ellipsis-${index}`} className="px-3 py-2 text-slate-400">...</span>
                  ) : (
                    <button
                      key={page}
                      onClick={() => handlePageChange(page)}
                      className={`px-4 py-2 rounded-lg font-medium transition-all ${
                        currentPage === page
                          ? 'bg-primary text-white'
                          : 'border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                      }`}
                    >
                      {page}
                    </button>
                  )
                ))}
              </div>
              
              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                <span className="material-symbols-outlined text-sm">chevron_right</span>
              </button>
            </div>
          </div>
        )}
      </div>
      </div>
      <Footer />
    </div>
  );
};

export default Dashboard;
