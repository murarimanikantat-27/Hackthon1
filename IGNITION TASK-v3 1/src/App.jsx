import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import MainContent from './components/MainContent';
import Footer from './components/Footer';
import Dashboard from './components/Dashboard';
import LoadingAnimation from './components/LoadingAnimation';

function App() {
  const [isDark, setIsDark] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [showLoading, setShowLoading] = useState(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
      setIsDark(true);
      document.documentElement.classList.add('dark');
    }
  }, []);

  const toggleTheme = () => {
    setIsDark(!isDark);
    if (!isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  };

  const handleFileUpload = (data) => {
    setShowLoading(true);
    setDashboardData(data);
  };

  const handleLoadingComplete = () => {
    setShowLoading(false);
  };

  const handleBackToUpload = () => {
    setDashboardData(null);
    setShowLoading(false);
  };

  // Show loading animation
  if (showLoading) {
    return <LoadingAnimation onComplete={handleLoadingComplete} />;
  }

  // Show dashboard after loading
  if (dashboardData && !showLoading) {
    return (
      <Dashboard data={dashboardData} onBack={handleBackToUpload} isDark={isDark} onThemeToggle={toggleTheme} />
    );
  }

  // Show upload page
  return (
    <div className="bg-background-light dark:bg-background-dark text-slate-900 dark:text-slate-100 min-h-screen flex flex-col overflow-x-hidden pt-16">
      <Header onThemeToggle={toggleTheme} isDark={isDark} />
      <MainContent onFileUpload={handleFileUpload} />
      <Footer />
    </div>
  );
}

export default App;
