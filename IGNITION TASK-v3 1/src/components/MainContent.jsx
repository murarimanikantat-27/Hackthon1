import React, { useState } from 'react';
import { API_BASE_URL } from '../config';

const MainContent = ({ onFileUpload }) => {
  const [selectedFile, setSelectedFile] = useState(null);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    setSelectedFile(file);
    
    if (file && file.type === 'application/json') {
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const jsonData = JSON.parse(event.target.result);
          
          // Transform array format to single object if needed
          let transformedData = jsonData;
          if (Array.isArray(jsonData) && jsonData.length > 0) {
            // Merge all check types into one result
            const allFailedChecks = [];
            const allPassedChecks = [];
            let totalPassed = 0;
            let totalFailed = 0;
            
            jsonData.forEach(item => {
              if (item.results) {
                allFailedChecks.push(...(item.results.failed_checks || []));
                allPassedChecks.push(...(item.results.passed_checks || []));
              }
              if (item.summary) {
                totalPassed += item.summary.passed || 0;
                totalFailed += item.summary.failed || 0;
              }
            });
            
            transformedData = {
              check_type: 'terraform',
              scanDate: new Date().toLocaleDateString(),
              projectName: 'Terraform Infrastructure Scan',
              results: {
                failed_checks: allFailedChecks,
                passed_checks: allPassedChecks
              },
              summary: {
                passed: totalPassed,
                failed: totalFailed
              }
            };
          }
          
          onFileUpload(transformedData);
        } catch (error) {
          alert('Invalid JSON file. Please upload a valid JSON file.');
        }
      };
      reader.readAsText(file);
    } else {
      alert('Please upload a JSON file.');
    }
  };

  return (
    <main className="flex-grow flex items-center py-12 overflow-x-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <div className="max-w-4xl mx-auto flex flex-col items-center">
          <div className="flex justify-center w-full">
            <div className="upload-area group relative flex flex-col items-center justify-center p-16 bg-white dark:bg-slate-900 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-[2.5rem] shadow-xl shadow-slate-200/50 dark:shadow-none hover:border-primary dark:hover:border-primary transition-all duration-300 w-full max-w-2xl cursor-pointer">
              <div className="upload-icon transition-transform duration-300 mb-8 bg-primary/5 dark:bg-primary/10 p-8 rounded-full">
                <span className="material-symbols-outlined text-7xl text-primary">cloud_upload</span>
              </div>
              <h2 className="text-3xl font-extrabold text-navy-deep dark:text-white mb-3">Upload your files here</h2>
              <p className="text-slate-500 dark:text-slate-400 mb-10 text-center text-lg max-w-md">
                Drag and drop your configuration files here to analyze deployment risks in real-time.
              </p>
              <label className="cursor-pointer group/btn">
                <span className="bg-navy-deep dark:bg-primary text-white px-10 py-4 rounded-xl font-bold hover:opacity-90 transition-all flex items-center gap-3 text-lg shadow-lg shadow-navy-deep/20 dark:shadow-primary/20">
                  <span className="material-symbols-outlined">upload_file</span>
                  Choose File
                </span>
                <input 
                  className="hidden" 
                  type="file" 
                  onChange={handleFileChange}
                  accept=".json"
                />
              </label>
              {selectedFile && (
                <p className="mt-4 text-sm text-slate-600 dark:text-slate-400">
                  Selected: {selectedFile.name}
                </p>
              )}
              <div className="mt-10 flex flex-col items-center gap-4">
                <p className="text-xs text-slate-400 uppercase tracking-[0.2em] font-semibold">Accepted Formats</p>
                <div className="flex gap-3">
                  <span className="px-3 py-1 bg-slate-100 dark:bg-slate-800 rounded-md text-[10px] font-bold text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700">JSON</span>
                </div>
              </div>
            </div>
          </div>
          <div className="mt-12 flex items-center gap-8 opacity-50">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-sm">verified_user</span>
              <span className="text-xs font-medium uppercase tracking-widest text-slate-500 dark:text-slate-400">Secure Transfer</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-sm">bolt</span>
              <span className="text-xs font-medium uppercase tracking-widest text-slate-500 dark:text-slate-400">Instant Analysis</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-sm">visibility_off</span>
              <span className="text-xs font-medium uppercase tracking-widest text-slate-500 dark:text-slate-400">Private &amp; Encrypted</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
};

export default MainContent;
