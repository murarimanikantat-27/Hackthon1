import React from 'react';
import logo from '../images/Shellkode-logo.png';

const Header = ({ onThemeToggle, isDark }) => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white/80 dark:bg-background-dark/80 border-b border-slate-200 dark:border-slate-800 glass-effect backdrop-blur-lg">
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center gap-8">
            <div className="flex-shrink-0 flex items-center">
              <div className="flex items-center gap-2">
                <img 
                  src={logo} 
                  alt="ShellKode Logo" 
                  className="h-10 w-auto"
                />
              </div>
            </div>
            <nav className="hidden md:flex space-x-8">
              <a className="text-slate-700 dark:text-slate-300 hover:text-primary dark:hover:text-primary font-semibold transition-colors text-base" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Platform</a>
              <a className="text-slate-700 dark:text-slate-300 hover:text-primary dark:hover:text-primary font-semibold transition-colors text-base" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Solutions</a>
              <a className="text-slate-700 dark:text-slate-300 hover:text-primary dark:hover:text-primary font-semibold transition-colors text-base" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Documentation</a>
              <a className="text-slate-700 dark:text-slate-300 hover:text-primary dark:hover:text-primary font-semibold transition-colors text-base" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Support</a>
            </nav>
          </div>
          <div className="flex items-center space-x-3">
            <button 
              className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors" 
              onClick={onThemeToggle}
            >
              <span className={`material-symbols-outlined text-xl ${isDark ? 'hidden' : 'block'}`}>dark_mode</span>
              <span className={`material-symbols-outlined text-xl ${isDark ? 'block' : 'hidden'}`}>light_mode</span>
            </button>
            <button className="bg-navy-deep text-white px-4 py-2 rounded-lg font-semibold hover:opacity-90 transition-all text-sm" onClick={() => window.open('https://www.shellkode.com', '_blank')}>
              Contact Sales
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
