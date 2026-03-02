import React, { useState, useEffect } from 'react';
import Header from './Header';
import Footer from './Footer';
import Sidebar from './Sidebar';
import { API_BASE_URL } from '../config';

const IncidentModal = ({ isOpen, onClose, isDark, onThemeToggle }) => {
  const [currentFilter, setCurrentFilter] = useState('all');
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);

  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    resolved: 0,
    failed: 0,
    critical: 0,
    high: 0,
    avgConfidence: 0
  });

  useEffect(() => {
    if (isOpen) {
      fetchIncidents();
    }
  }, [isOpen]);

  useEffect(() => {
    if (incidents.length > 0) {
      calculateStats();
    }
  }, [incidents]);

  const fetchIncidents = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/incidents?limit=100`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setIncidents(data);
    } catch (err) {
      console.error('Error fetching incidents:', err);
      setError(err.message || 'Failed to fetch incidents');
      setIncidents([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchIncidentDetails = async (id) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/incidents/${id}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      // Transform API response to match component expectations
      const transformedData = {
        ...data.incident,
        rca: data.rca_reports && data.rca_reports.length > 0 ? data.rca_reports[0] : null,
        actions: data.remediation_actions || []
      };
      setSelectedIncident(transformedData);
    } catch (err) {
      console.error('Error fetching incident details:', err);
    }
  };

  const calculateStats = () => {
    const total = incidents.length;
    const active = incidents.filter(i => !['resolved', 'failed'].includes(i.status)).length;
    const resolved = incidents.filter(i => i.status === 'resolved').length;
    const failed = incidents.filter(i => i.status === 'failed').length;
    const critical = incidents.filter(i => i.severity === 'critical').length;
    const high = incidents.filter(i => i.severity === 'high').length;
    const avgConfidence = incidents.reduce((sum, i) => sum + (i.rca?.confidence_score || 0), 0) / total;

    setStats({ total, active, resolved, failed, critical, high, avgConfidence });
  };

  const getFilteredIncidents = () => {
    if (currentFilter === 'all') return incidents;
    if (['critical', 'high', 'medium', 'low', 'info'].includes(currentFilter)) {
      return incidents.filter(i => i.severity === currentFilter);
    }
    return incidents.filter(i => i.status === currentFilter);
  };

  const handleIncidentClick = (incident) => {
    setSelectedIncident(incident);
    // Optionally fetch fresh details from API
    fetchIncidentDetails(incident.id);
  };

  const timeAgo = (dateStr) => {
    const now = new Date();
    const date = new Date(dateStr);
    const seconds = Math.floor((now - date) / 1000);
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
    return Math.floor(seconds / 86400) + 'd ago';
  };

  const handleDownloadPDF = (incident) => {
    window.open(`${API_BASE_URL}/api/incidents/${incident.id}/pdf`, '_blank');
  };

  const handleApproveRemediation = async (incident) => {
    setIsExecuting(true);
    setExecutionResult(null);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/incidents/${incident.id}/remediate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Set execution result to show in modal
      setExecutionResult({
        success: true,
        status: data.status,
        command: data.action?.command || 'N/A',
        output: data.action?.output || 'No output available'
      });
      
      // Refresh incident data
      const updatedResponse = await fetch(`${API_BASE_URL}/api/incidents/${incident.id}`);
      if (updatedResponse.ok) {
        const updatedData = await updatedResponse.json();
        const transformedData = {
          ...updatedData.incident,
          rca: updatedData.rca_reports && updatedData.rca_reports.length > 0 ? updatedData.rca_reports[0] : null,
          actions: updatedData.remediation_actions || []
        };
        setSelectedIncident(transformedData);
        
        // Update incidents list
        const allIncidentsResponse = await fetch(`${API_BASE_URL}/api/incidents?limit=100`);
        if (allIncidentsResponse.ok) {
          const allIncidents = await allIncidentsResponse.json();
          setIncidents(allIncidents);
        }
      }
    } catch (err) {
      console.error('Error executing remediation:', err);
      setExecutionResult({
        success: false,
        error: err.message
      });
    } finally {
      setIsExecuting(false);
    }
  };

  const closeExecutionModal = () => {
    setExecutionResult(null);
  };

  if (!isOpen) return null;

  const filteredIncidents = getFilteredIncidents();

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark flex flex-col pt-16">
      <Header onThemeToggle={onThemeToggle} isDark={isDark} />
      <Sidebar 
        onIncidentClick={() => {}} 
        onVulnerabilitiesClick={onClose}
        activeItem="incidents"
      />
      
      {/* Execution Result Modal */}
      {executionResult && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-y-auto border border-slate-200 dark:border-slate-800">
            <div className={`px-8 py-6 border-b border-slate-200 dark:border-slate-800 ${
              executionResult.success ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'
            }`}>
              <div className="flex items-center gap-4">
                <div className={`w-16 h-16 rounded-full flex items-center justify-center ${
                  executionResult.success ? 'bg-green-500' : 'bg-red-500'
                }`}>
                  <span className="material-symbols-outlined text-white text-4xl">
                    {executionResult.success ? 'check_circle' : 'error'}
                  </span>
                </div>
                <div>
                  <h2 className={`text-2xl font-bold ${
                    executionResult.success ? 'text-green-800 dark:text-green-400' : 'text-red-800 dark:text-red-400'
                  }`}>
                    {executionResult.success ? 'Remediation Executed Successfully!' : 'Remediation Failed'}
                  </h2>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                    {executionResult.success ? 'The remediation command has been executed' : 'An error occurred during execution'}
                  </p>
                </div>
              </div>
            </div>

            <div className="px-8 py-6 space-y-6">
              {executionResult.success ? (
                <>
                  <div>
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-2">Status</div>
                    <div className="px-4 py-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                      <span className="text-green-800 dark:text-green-400 font-semibold">{executionResult.status}</span>
                    </div>
                  </div>

                  <div>
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-2">Command Executed</div>
                    <div className="font-mono text-sm px-4 py-3 bg-slate-900 dark:bg-black rounded-lg text-cyan-400 overflow-x-auto">
                      {executionResult.command}
                    </div>
                  </div>

                  <div>
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-2">Output</div>
                    <div className="px-4 py-3 bg-slate-50 dark:bg-slate-800 rounded-lg max-h-60 overflow-y-auto">
                      <pre className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-mono">
                        {executionResult.output}
                      </pre>
                    </div>
                  </div>
                </>
              ) : (
                <div>
                  <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-2">Error Details</div>
                  <div className="px-4 py-3 bg-red-50 dark:bg-red-900/20 rounded-lg border-l-4 border-red-500">
                    <p className="text-sm text-red-800 dark:text-red-400">{executionResult.error}</p>
                  </div>
                </div>
              )}
            </div>

            <div className="px-8 py-6 border-t border-slate-200 dark:border-slate-800 flex justify-end">
              <button
                onClick={closeExecutionModal}
                className="px-8 py-3 bg-primary hover:bg-primary/90 text-white rounded-lg font-semibold transition-all shadow-lg hover:shadow-xl"
              >
                OK
              </button>
            </div>
          </div>
        </div>
      )}
      
      <div className="flex-1 bg-background-light dark:bg-background-dark overflow-y-auto overflow-x-auto py-8">
        <div className="w-full pl-4 sm:pl-6 lg:pl-8 pr-2 sm:pr-3 lg:pr-4 ml-64 mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h1 className="text-3xl font-bold text-navy-deep dark:text-white">
                Incident Command Center
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-green-100 dark:bg-green-900/30 border border-green-200 dark:border-green-900 text-green-800 dark:text-green-400 text-sm font-medium">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                Agent Active
              </div>
              <button 
                onClick={onClose} 
                className="flex items-center gap-2 px-4 py-2 bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg hover:opacity-80 transition-all"
              >
                <span className="material-symbols-outlined">arrow_back</span>
                Back to Dashboard
              </button>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="w-full pl-4 sm:pl-6 lg:pl-8 pr-2 sm:pr-3 lg:pr-4 ml-64">
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4"></div>
                <p className="text-slate-600 dark:text-slate-400">Loading incidents...</p>
              </div>
            </div>
          </div>
        ) : error ? (
          <div className="w-full pl-4 sm:pl-6 lg:pl-8 pr-2 sm:pr-3 lg:pr-4 ml-64">
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900 rounded-xl p-6">
              <div className="flex items-center gap-3 mb-4">
                <span className="material-symbols-outlined text-red-600 dark:text-red-400">error</span>
                <div>
                  <h3 className="text-lg font-bold text-red-800 dark:text-red-400">Error Loading Incidents</h3>
                  <p className="text-sm text-red-600 dark:text-red-400 mt-1">{error}</p>
                </div>
              </div>
              <button 
                onClick={fetchIncidents}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-all"
              >
                Retry
              </button>
            </div>
          </div>
        ) : (
          <>
        <div className="w-full pl-4 sm:pl-6 lg:pl-8 pr-2 sm:pr-3 lg:pr-4 ml-64">
          <div className="overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-slate-400 scrollbar-track-slate-200 dark:scrollbar-thumb-slate-600 dark:scrollbar-track-slate-800">
            <div className="flex gap-4 mb-8 min-w-max">
            {[
              { label: 'Total Incidents', value: stats.total, color: 'text-primary', bgColor: 'bg-blue-50 dark:bg-blue-900/20', borderColor: 'border-blue-200 dark:border-blue-900' },
              { label: 'Active', value: stats.active, color: 'text-amber-600 dark:text-amber-400', bgColor: 'bg-amber-50 dark:bg-amber-900/20', borderColor: 'border-amber-200 dark:border-amber-900' },
              { label: 'Resolved', value: stats.resolved, color: 'text-green-600 dark:text-green-400', bgColor: 'bg-green-50 dark:bg-green-900/20', borderColor: 'border-green-200 dark:border-green-900' },
              { label: 'Failed', value: stats.failed, color: 'text-red-600 dark:text-red-400', bgColor: 'bg-red-50 dark:bg-red-900/20', borderColor: 'border-red-200 dark:border-red-900' },
              { label: 'Critical', value: stats.critical, color: 'text-red-600 dark:text-red-400', bgColor: 'bg-red-50 dark:bg-red-900/20', borderColor: 'border-red-200 dark:border-red-900' },
              { label: 'High', value: stats.high, color: 'text-orange-600 dark:text-orange-400', bgColor: 'bg-orange-50 dark:bg-orange-900/20', borderColor: 'border-orange-200 dark:border-orange-900' },
              { label: 'Avg Confidence', value: stats.avgConfidence > 0 ? `${(stats.avgConfidence * 100).toFixed(0)}%` : '—', color: 'text-purple-600 dark:text-purple-400', bgColor: 'bg-purple-50 dark:bg-purple-900/20', borderColor: 'border-purple-200 dark:border-purple-900' }
            ].map((stat, i) => (
              <div key={i} className={`${stat.bgColor} border ${stat.borderColor} rounded-xl p-6 hover:shadow-lg transition-all flex-shrink-0 w-48`}>
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-2">{stat.label}</div>
                <div className={`text-3xl font-extrabold ${stat.color}`}>
                  {stat.value}
                </div>
              </div>
            ))}
          </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-6">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-lg">
              <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                <div className="text-lg font-bold text-navy-deep dark:text-white flex items-center gap-2">
                  🚨 Incidents
                </div>
                <span className="text-sm text-slate-500 dark:text-slate-400">{filteredIncidents.length} incidents</span>
              </div>

              <div className="flex gap-2 px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex-wrap">
                {['all', 'critical', 'high', 'medium', 'resolved', 'failed'].map(filter => (
                  <button
                    key={filter}
                    onClick={() => setCurrentFilter(filter)}
                    className={`px-3.5 py-1.5 rounded-full border text-xs font-medium transition-all ${
                      currentFilter === filter
                        ? 'bg-primary text-white border-primary'
                        : 'border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    {filter.charAt(0).toUpperCase() + filter.slice(1)}
                  </button>
                ))}
              </div>

              <div className="max-h-[600px] overflow-y-auto">
                {filteredIncidents.map(inc => (
                  <div
                    key={inc.id}
                    onClick={() => handleIncidentClick(inc)}
                    className={`px-6 py-4 border-b border-slate-200 dark:border-slate-800 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-all flex items-start gap-3.5 ${
                      selectedIncident?.id === inc.id ? 'bg-primary/10 dark:bg-primary/20 border-l-4 border-l-primary' : ''
                    }`}
                  >
                    <div className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 ${
                      inc.severity === 'critical' ? 'bg-red-500' :
                      inc.severity === 'high' ? 'bg-orange-500' :
                      inc.severity === 'medium' ? 'bg-yellow-500' :
                      'bg-blue-500'
                    }`}></div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-navy-deep dark:text-white mb-1.5 truncate">{inc.title}</div>
                      <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                        <span className="px-2 py-0.5 rounded bg-primary/10 dark:bg-primary/20 text-primary font-mono text-[11px] font-medium">{inc.namespace}</span>
                        <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase ${
                          inc.status === 'resolved' ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400' :
                          inc.status === 'failed' ? 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400' :
                          'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400'
                        }`}>{inc.status}</span>
                        <span>{timeAgo(inc.detected_at)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-lg">
              <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                <div className="text-lg font-bold text-navy-deep dark:text-white">📋 Incident Details</div>
              </div>
              <div className="max-h-[700px] overflow-y-auto">
                {!selectedIncident ? (
                  <div className="flex flex-col items-center justify-center py-20 px-10 text-slate-500 dark:text-slate-400 text-center">
                    <div className="text-6xl opacity-40 mb-4">🔍</div>
                    <p>Select an incident to view details</p>
                    <p className="text-xs mt-2">Click on any incident from the list</p>
                  </div>
                ) : (
                  <>
                    <div className="px-6 py-6 border-b border-slate-200 dark:border-slate-800">
                      <div className="flex items-center gap-2.5 mb-2">
                        <div className={`w-2.5 h-2.5 rounded-full ${
                          selectedIncident.severity === 'critical' ? 'bg-red-500' :
                          selectedIncident.severity === 'high' ? 'bg-orange-500' :
                          selectedIncident.severity === 'medium' ? 'bg-yellow-500' :
                          'bg-blue-500'
                        }`}></div>
                        <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase ${
                          selectedIncident.status === 'resolved' ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400' :
                          selectedIncident.status === 'failed' ? 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400' :
                          'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400'
                        }`}>{selectedIncident.status}</span>
                        <span className="text-xs text-slate-500 dark:text-slate-400">ID #{selectedIncident.id}</span>
                      </div>
                      <h2 className="text-lg font-bold text-navy-deep dark:text-white mb-2">{selectedIncident.title}</h2>
                      <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                        <span className="px-2 py-0.5 rounded bg-primary/10 dark:bg-primary/20 text-primary font-mono">{selectedIncident.namespace}</span>
                        <span>{selectedIncident.resource_type} / {selectedIncident.resource_name}</span>
                        <span>{timeAgo(selectedIncident.detected_at)}</span>
                      </div>
                    </div>

                    {selectedIncident.rca && (
                      <>
                        {/* Executive Summary */}
                        {selectedIncident.rca.executive_summary && (
                          <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-3">📊 1. Executive Summary</div>
                            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">{selectedIncident.rca.executive_summary}</p>
                          </div>
                        )}

                        {/* Incident Detection */}
                        {selectedIncident.rca.incident_detection && (
                          <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-3">🔍 2. Incident Detection</div>
                            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">{selectedIncident.rca.incident_detection}</p>
                          </div>
                        )}

                        {/* Incident Timeline */}
                        {selectedIncident.rca.incident_timeline && selectedIncident.rca.incident_timeline.length > 0 && (
                          <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-3">⏱️ 3. Incident Timeline (UTC)</div>
                            <ul className="space-y-2">
                              {selectedIncident.rca.incident_timeline.map((item, i) => (
                                <li key={i} className="flex items-start gap-2.5 text-sm text-slate-600 dark:text-slate-400">
                                  <span className="text-primary font-bold flex-shrink-0">•</span>
                                  {item}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Root Cause Analysis */}
                        <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                          <div className="flex items-center justify-between mb-3">
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400">🧠 4. Root Cause Analysis</div>
                            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                              Confidence: {(selectedIncident.rca.confidence_score * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden mb-4">
                            <div
                              className={`h-full rounded-full transition-all ${
                                selectedIncident.rca.confidence_score >= 0.7 ? 'bg-green-500' :
                                selectedIncident.rca.confidence_score >= 0.4 ? 'bg-yellow-500' :
                                'bg-red-500'
                              }`}
                              style={{ width: `${selectedIncident.rca.confidence_score * 100}%` }}
                            ></div>
                          </div>
                          <div className="text-sm font-semibold text-navy-deep dark:text-white px-4 py-3 bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 rounded-r-lg mb-3">
                            {selectedIncident.rca.root_cause}
                          </div>
                          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">{selectedIncident.rca.analysis}</p>
                        </div>

                        {/* Impact Assessment */}
                        {selectedIncident.rca.impact_assessment && (
                          <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-3">💥 5. Impact Assessment</div>
                            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 whitespace-pre-line">{selectedIncident.rca.impact_assessment}</p>
                          </div>
                        )}

                        {/* Resolution Actions */}
                        {selectedIncident.rca.resolution_actions && (
                          <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-3">⚡ 6. Resolution Actions</div>
                            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 whitespace-pre-line">{selectedIncident.rca.resolution_actions}</p>
                          </div>
                        )}

                        {/* AI-Suggested Remediation Command */}
                        {selectedIncident.rca.remediation_command && (
                          <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-3">🤖 AI-Suggested Remediation Command</div>
                            <div className="mb-3">
                              <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold uppercase ${
                                selectedIncident.rca.remediation_risk === 'low' ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400' :
                                selectedIncident.rca.remediation_risk === 'medium' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-400' :
                                'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400'
                              }`}>Risk: {selectedIncident.rca.remediation_risk}</span>
                            </div>
                            <div className="font-mono text-sm px-4 py-3 bg-slate-900 dark:bg-black rounded-lg text-cyan-400 overflow-x-auto mb-3">
                              $ kubectl {selectedIncident.rca.remediation_command}
                            </div>
                            {selectedIncident.rca.remediation_explanation && (
                              <div className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                                <span className="font-semibold text-navy-deep dark:text-white">💡 Why: </span>
                                {selectedIncident.rca.remediation_explanation}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Preventive Measures */}
                        {selectedIncident.rca.preventive_measures && (
                          <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-3">🛡️ 7. Preventive Measures</div>
                            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 whitespace-pre-line">{selectedIncident.rca.preventive_measures}</p>
                          </div>
                        )}

                        {/* Lessons Learned */}
                        {selectedIncident.rca.lessons_learned && (
                          <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-3">🎓 8. Lessons Learned</div>
                            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 whitespace-pre-line">{selectedIncident.rca.lessons_learned}</p>
                          </div>
                        )}

                        {/* Final Summary */}
                        {selectedIncident.rca.final_summary && (
                          <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-3">📝 9. Final Summary</div>
                            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 whitespace-pre-line">{selectedIncident.rca.final_summary}</p>
                          </div>
                        )}
                      </>
                    )}

                    <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
                      <div className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400 mb-3">🔧 Remediation History</div>
                      {selectedIncident.actions && selectedIncident.actions.length > 0 ? (
                        selectedIncident.actions.map((action, i) => (
                          <div key={i} className="px-4 py-3 mb-2 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                            <div className="flex justify-between items-center mb-2">
                              <span className="text-sm font-semibold text-navy-deep dark:text-white">{action.action_type || 'Remediation'}</span>
                              <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase ${
                                action.status === 'success' ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400' :
                                action.status === 'failed' ? 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400' :
                                'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400'
                              }`}>{action.status}</span>
                            </div>
                            {action.command && (
                              <div className="font-mono text-xs px-3 py-2 bg-slate-900 dark:bg-black rounded-md text-cyan-400 overflow-x-auto">
                                $ {action.command}
                              </div>
                            )}
                            {action.output && (
                              <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">{action.output}</p>
                            )}
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-slate-500 dark:text-slate-400">No remediation actions taken yet.</p>
                      )}
                    </div>

                    <div className="px-6 py-5 flex gap-3">
                      <button
                        onClick={() => handleDownloadPDF(selectedIncident)}
                        disabled={isExecuting}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span className="material-symbols-outlined text-lg">download</span>
                        Download PDF
                      </button>
                      <button
                        onClick={() => handleApproveRemediation(selectedIncident)}
                        disabled={isExecuting}
                        className="flex-[2] flex items-center justify-center gap-2 px-4 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-all shadow-lg hover:shadow-xl disabled:opacity-70 disabled:cursor-not-allowed relative overflow-hidden"
                      >
                        {isExecuting ? (
                          <>
                            <div className="absolute inset-0 bg-gradient-to-r from-green-600 via-green-500 to-green-600 animate-pulse"></div>
                            <div className="relative flex items-center gap-2">
                              <div className="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                              <span>Executing Remediation...</span>
                            </div>
                          </>
                        ) : (
                          <>
                            <span className="material-symbols-outlined text-lg">check_circle</span>
                            Approve & Execute Remediation
                          </>
                        )}
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
        </>
        )}
      </div>
      
      <Footer />
    </div>
  );
};

export default IncidentModal;
