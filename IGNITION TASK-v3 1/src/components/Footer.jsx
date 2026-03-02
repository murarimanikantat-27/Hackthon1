import React from 'react';
import logo from '../images/Shellkode-logo.png';

const Footer = () => {
  return (
    <footer className="mt-auto relative z-40 bg-white dark:bg-slate-950 border-t border-slate-200 dark:border-slate-800 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 md:gap-8">
          <div className="col-span-1 md:col-span-2">
            <div className="flex items-center gap-3 mb-6">
              <img 
                src={logo} 
                alt="ShellKode Logo" 
                className="h-8 w-auto"
              />
            </div>
            <p className="text-slate-500 dark:text-slate-400 max-w-sm">
              Empowering engineering teams with AI-driven insights to build, deploy, and scale cloud infrastructure with maximum security.
            </p>
          </div>
          <div>
            <h4 className="text-navy-deep dark:text-white font-bold mb-4 uppercase text-xs tracking-widest">Resources</h4>
            <ul className="space-y-2 text-sm text-slate-500 dark:text-slate-400">
              <li><a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Documentation</a></li>
              <li><a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">AI Model Insights</a></li>
              <li><a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Community</a></li>
              <li><a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Status</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-navy-deep dark:text-white font-bold mb-4 uppercase text-xs tracking-widest">Legal</h4>
            <ul className="space-y-2 text-sm text-slate-500 dark:text-slate-400">
              <li><a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Privacy Policy</a></li>
              <li><a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Terms of Service</a></li>
              <li><a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Security</a></li>
              <li><a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Compliance</a></li>
            </ul>
          </div>
        </div>
        <div className="mt-12 pt-8 border-t border-slate-100 dark:border-slate-900 flex flex-col md:flex-row justify-between items-center text-sm text-slate-400">
          <p>© 2024 ShellKode Inc. All rights reserved.</p>
          <div className="flex space-x-6 mt-4 md:mt-0">
            <a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">Twitter</a>
            <a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">LinkedIn</a>
            <a className="hover:text-primary transition-colors" href="https://www.shellkode.com" target="_blank" rel="noopener noreferrer">GitHub</a>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
