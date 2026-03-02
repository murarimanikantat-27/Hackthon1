import React, { useState } from 'react';

const Sidebar = ({ onIncidentClick, onVulnerabilitiesClick, activeItem }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <>
      {/* Sidebar */}
      <div className={`fixed left-0 top-16 h-[calc(100vh-4rem)] bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 transition-all duration-300 z-30 ${isCollapsed ? 'w-16' : 'w-64'}`}>
        <div className="flex flex-col h-full">
          {/* Toggle Button */}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="absolute -right-3 top-6 w-6 h-6 bg-primary rounded-full flex items-center justify-center text-white hover:opacity-80 transition-all shadow-lg"
          >
            <span className="material-symbols-outlined text-sm">
              {isCollapsed ? 'chevron_right' : 'chevron_left'}
            </span>
          </button>

          {/* Sidebar Content */}
          <div className="flex-1 overflow-y-auto py-6">
            <nav className="space-y-2 px-3">
              {/* Dashboard */}
              <button 
                onClick={() => {
                  if (onVulnerabilitiesClick) onVulnerabilitiesClick();
                }}
                className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-all ${
                  activeItem === 'dashboard' 
                    ? 'bg-primary text-white' 
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <span className="material-symbols-outlined">dashboard</span>
                {!isCollapsed && <span className="font-medium">Dashboard</span>}
              </button>

              {/* Vulnerabilities */}
              <button 
                onClick={() => {
                  if (onVulnerabilitiesClick) onVulnerabilitiesClick();
                }}
                className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-all ${
                  activeItem === 'vulnerabilities' 
                    ? 'bg-primary text-white' 
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <span className="material-symbols-outlined">bug_report</span>
                {!isCollapsed && <span className="font-medium">Vulnerabilities</span>}
              </button>

              {/* Incident Button */}
              <button 
                onClick={() => {
                  if (onIncidentClick) onIncidentClick();
                }}
                className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-all ${
                  activeItem === 'incidents' 
                    ? 'bg-primary text-white' 
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <span className="material-symbols-outlined">warning</span>
                {!isCollapsed && <span className="font-medium">Incidents</span>}
              </button>

              {/* Reports */}
              <button 
                className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-all ${
                  activeItem === 'reports' 
                    ? 'bg-primary text-white' 
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <span className="material-symbols-outlined">assessment</span>
                {!isCollapsed && <span className="font-medium">Reports</span>}
              </button>

              {/* Settings */}
              <button 
                className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-all ${
                  activeItem === 'settings' 
                    ? 'bg-primary text-white' 
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <span className="material-symbols-outlined">settings</span>
                {!isCollapsed && <span className="font-medium">Settings</span>}
              </button>
            </nav>
          </div>

          {/* User Section */}
          {!isCollapsed && (
            <div className="border-t border-slate-200 dark:border-slate-800 p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary rounded-full flex items-center justify-center text-white font-bold">
                  U
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-white truncate">User</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">user@shellkode.com</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default Sidebar;
