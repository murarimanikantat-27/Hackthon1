import React, { useState } from 'react';
import { API_BASE_URL } from '../config';

const MainContent = ({ onFileUpload }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    setSelectedFile(file);
    setUploadError(null);
    
    const filename = file.name.toLowerCase();
    const isValidFile = filename.endsWith('.tf') || filename.endsWith('.zip') || filename.endsWith('.tar.gz');
    
    if (file && isValidFile) {
      setIsUploading(true);
      
      try {
        // Create FormData to upload the file
        const formData = new FormData();
        formData.append('file', file);
        
        // Call the Checkov API
        const response = await fetch(`${API_BASE_URL}/api/v1/terraform/checkov`, {
          method: 'POST',
          body: formData
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to analyze Terraform file');
        }
        
        const checkovResult = await response.json();
        
        // Transform Checkov result to dashboard format
        const transformedData = transformCheckovResult(checkovResult, file.name);
        
        onFileUpload(transformedData);
      } catch (error) {
        console.error('Error uploading file:', error);
        setUploadError(error.message);
        setIsUploading(false);
      }
    } else {
      setUploadError('Please upload a .tf file, .zip, or .tar.gz archive containing Terraform scripts.');
    }
  };

  const transformCheckovResult = (checkovData, filename) => {
    // Extract checks from Checkov response
    const allFailedChecks = [];
    const allPassedChecks = [];
    let totalPassed = 0;
    let totalFailed = 0;
    
    // Checkov returns an array of results
    if (Array.isArray(checkovData)) {
      checkovData.forEach(item => {
        if (item.results) {
          allFailedChecks.push(...(item.results.failed_checks || []));
          allPassedChecks.push(...(item.results.passed_checks || []));
        }
        if (item.summary) {
          totalPassed += item.summary.passed || 0;
          totalFailed += item.summary.failed || 0;
        }
      });
    } else if (checkovData.results) {
      // Single result object
      allFailedChecks.push(...(checkovData.results.failed_checks || []));
      allPassedChecks.push(...(checkovData.results.passed_checks || []));
      if (checkovData.summary) {
        totalPassed = checkovData.summary.passed || 0;
        totalFailed = checkovData.summary.failed || 0;
      }
    }
    
    return {
      check_type: 'terraform',
      scanDate: new Date().toLocaleDateString(),
      projectName: `Terraform Security Scan - ${filename}`,
      results: {
        failed_checks: allFailedChecks,
        passed_checks: allPassedChecks
      },
      summary: {
        passed: totalPassed,
        failed: totalFailed
      }
    };
  };

  return (
    <main className="flex-grow flex items-center py-12 overflow-x-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <div className="max-w-4xl mx-auto flex flex-col items-center">
          <div className="flex justify-center w-full">
            <div className="upload-area group relative flex flex-col items-center justify-center p-16 bg-white dark:bg-slate-900 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-[2.5rem] shadow-xl shadow-slate-200/50 dark:shadow-none hover:border-primary dark:hover:border-primary transition-all duration-300 w-full max-w-2xl cursor-pointer">
              {isUploading ? (
                <div className="flex flex-col items-center">
                  <div className="inline-block animate-spin rounded-full h-16 w-16 border-b-4 border-primary mb-6"></div>
                  <h2 className="text-2xl font-extrabold text-navy-deep dark:text-white mb-2">Analyzing Terraform Files...</h2>
                  <p className="text-slate-500 dark:text-slate-400 text-center">
                    Running security checks with Checkov
                  </p>
                </div>
              ) : (
                <>
                  <div className="upload-icon transition-transform duration-300 mb-8 bg-primary/5 dark:bg-primary/10 p-8 rounded-full">
                    <span className="material-symbols-outlined text-7xl text-primary">cloud_upload</span>
                  </div>
                  <h2 className="text-3xl font-extrabold text-navy-deep dark:text-white mb-3">Upload Terraform Files</h2>
                  <p className="text-slate-500 dark:text-slate-400 mb-10 text-center text-lg max-w-md">
                    Upload your .tf file, or a .zip/.tar.gz archive containing Terraform configurations to analyze security vulnerabilities.
                  </p>
                  <label className="cursor-pointer group/btn">
                    <span className="bg-navy-deep dark:bg-primary text-white px-10 py-4 rounded-xl font-bold hover:opacity-90 transition-all flex items-center gap-3 text-lg shadow-lg shadow-navy-deep/20 dark:shadow-primary/20">
                      <span className="material-symbols-outlined">upload_file</span>
                      Choose File or Archive
                    </span>
                    <input 
                      className="hidden" 
                      type="file" 
                      onChange={handleFileChange}
                      accept=".tf,.zip,.tar.gz"
                      disabled={isUploading}
                    />
                  </label>
                  {selectedFile && !uploadError && (
                    <p className="mt-4 text-sm text-slate-600 dark:text-slate-400">
                      Selected: {selectedFile.name}
                    </p>
                  )}
                  {uploadError && (
                    <div className="mt-4 px-4 py-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900 rounded-lg">
                      <p className="text-sm text-red-600 dark:text-red-400">{uploadError}</p>
                    </div>
                  )}
                  <div className="mt-10 flex flex-col items-center gap-4">
                    <p className="text-xs text-slate-400 uppercase tracking-[0.2em] font-semibold">Accepted Formats</p>
                    <div className="flex gap-3">
                      <span className="px-3 py-1 bg-slate-100 dark:bg-slate-800 rounded-md text-[10px] font-bold text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700">.TF</span>
                      <span className="px-3 py-1 bg-slate-100 dark:bg-slate-800 rounded-md text-[10px] font-bold text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700">.ZIP</span>
                      <span className="px-3 py-1 bg-slate-100 dark:bg-slate-800 rounded-md text-[10px] font-bold text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700">.TAR.GZ</span>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
          <div className="mt-12 flex items-center gap-8 opacity-50">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-sm">verified_user</span>
              <span className="text-xs font-medium uppercase tracking-widest text-slate-500 dark:text-slate-400">Secure Analysis</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-sm">bolt</span>
              <span className="text-xs font-medium uppercase tracking-widest text-slate-500 dark:text-slate-400">Instant Results</span>
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
