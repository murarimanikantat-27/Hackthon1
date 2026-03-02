import React from 'react';
import logo from '../images/Shellkode-logo-hi-res.svg';

const HomePage = ({ onContinue }) => {
  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark flex items-center justify-center overflow-hidden relative">
      {/* Animated background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-cyan-500/10"></div>
      <div className="absolute inset-0 bg-gradient-to-tr from-purple-500/5 via-transparent to-primary/5 animate-pulse"></div>
      
      {/* Floating particles effect */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-primary/5 rounded-full blur-3xl animate-float"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl animate-float-delayed"></div>
        <div className="absolute top-1/2 right-1/3 w-48 h-48 bg-purple-500/5 rounded-full blur-3xl animate-float-slow"></div>
      </div>

      {/* Main content */}
      <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        {/* Logo */}
        <div className="flex justify-center mb-12 animate-fade-in-down">
          <img
            src={logo}
            alt="ShellKode"
            className="w-48 h-48 object-contain drop-shadow-2xl animate-float"
          />
        </div>

        {/* Main heading */}
        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold text-navy-deep dark:text-white mb-6 animate-fade-in-up leading-tight">
          AI-Powered Deployment
          <br />
          <span className="bg-gradient-to-r from-primary via-cyan-500 to-purple-500 bg-clip-text text-transparent animate-gradient">
            Risk Predictor
          </span>
        </h1>

        {/* Subtitle */}
        <p className="text-xl sm:text-2xl text-slate-600 dark:text-slate-400 mb-12 max-w-3xl mx-auto animate-fade-in-up animation-delay-200 leading-relaxed">
          Analyze your infrastructure configurations with advanced AI to identify security vulnerabilities and deployment risks before they impact your production environment.
        </p>

        {/* Features grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12 animate-fade-in-up animation-delay-400">
          <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-200 dark:border-slate-800 hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
            <div className="w-14 h-14 bg-primary/10 rounded-xl flex items-center justify-center mx-auto mb-4">
              <span className="material-symbols-outlined text-3xl text-primary">security</span>
            </div>
            <h3 className="text-lg font-bold text-navy-deep dark:text-white mb-2">Security Analysis</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">Real-time threat detection and vulnerability assessment</p>
          </div>

          <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-200 dark:border-slate-800 hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
            <div className="w-14 h-14 bg-cyan-500/10 rounded-xl flex items-center justify-center mx-auto mb-4">
              <span className="material-symbols-outlined text-3xl text-cyan-500">psychology</span>
            </div>
            <h3 className="text-lg font-bold text-navy-deep dark:text-white mb-2">AI-Powered Insights</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">Machine learning algorithms for predictive analysis</p>
          </div>

          <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-200 dark:border-slate-800 hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
            <div className="w-14 h-14 bg-purple-500/10 rounded-xl flex items-center justify-center mx-auto mb-4">
              <span className="material-symbols-outlined text-3xl text-purple-500">speed</span>
            </div>
            <h3 className="text-lg font-bold text-navy-deep dark:text-white mb-2">Instant Results</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">Get comprehensive reports in seconds</p>
          </div>
        </div>

        {/* Continue button */}
        <div className="animate-fade-in-up animation-delay-600">
          <button
            onClick={onContinue}
            className="group relative inline-flex items-center gap-3 px-12 py-5 bg-gradient-to-r from-primary to-cyan-500 text-white text-xl font-bold rounded-2xl shadow-2xl hover:shadow-primary/50 transition-all duration-300 hover:scale-105 overflow-hidden"
          >
            <span className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-primary opacity-0 group-hover:opacity-100 transition-opacity duration-300"></span>
            <span className="relative">Continue</span>
            <span className="material-symbols-outlined relative text-2xl group-hover:translate-x-1 transition-transform duration-300">arrow_forward</span>
          </button>
        </div>

        {/* Trust indicators */}
        <div className="mt-16 flex items-center justify-center gap-8 text-sm text-slate-500 dark:text-slate-400 animate-fade-in animation-delay-800">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-green-500">verified</span>
            <span>Enterprise Grade</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-green-500">lock</span>
            <span>Secure & Private</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-green-500">bolt</span>
            <span>Lightning Fast</span>
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-20px); }
        }
        
        @keyframes float-delayed {
          0%, 100% { transform: translateY(0px) translateX(0px); }
          50% { transform: translateY(-30px) translateX(20px); }
        }
        
        @keyframes float-slow {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-15px); }
        }
        
        @keyframes gradient {
          0%, 100% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
        }
        
        .animate-float {
          animation: float 6s ease-in-out infinite;
        }
        
        .animate-float-delayed {
          animation: float-delayed 8s ease-in-out infinite;
        }
        
        .animate-float-slow {
          animation: float-slow 10s ease-in-out infinite;
        }
        
        .animate-gradient {
          background-size: 200% 200%;
          animation: gradient 3s ease infinite;
        }
        
        .animate-fade-in-down {
          animation: fadeInDown 0.8s ease-out;
        }
        
        .animate-fade-in-up {
          animation: fadeInUp 0.8s ease-out;
        }
        
        .animate-fade-in {
          animation: fadeIn 1s ease-out;
        }
        
        .animation-delay-200 {
          animation-delay: 0.2s;
          opacity: 0;
          animation-fill-mode: forwards;
        }
        
        .animation-delay-400 {
          animation-delay: 0.4s;
          opacity: 0;
          animation-fill-mode: forwards;
        }
        
        .animation-delay-600 {
          animation-delay: 0.6s;
          opacity: 0;
          animation-fill-mode: forwards;
        }
        
        .animation-delay-800 {
          animation-delay: 0.8s;
          opacity: 0;
          animation-fill-mode: forwards;
        }
        
        @keyframes fadeInDown {
          from {
            opacity: 0;
            transform: translateY(-30px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(30px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
};

export default HomePage;
