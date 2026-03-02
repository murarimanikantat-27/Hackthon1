import React, { useEffect, useState } from 'react';
import logo from '../images/Shellkode-logo-hi-res.svg';

const LoadingAnimation = ({ onComplete }) => {
  const [stage, setStage] = useState('zoom-in'); // zoom-in, hold, zoom-out

  useEffect(() => {
    // Zoom in and hold
    const holdTimer = setTimeout(() => {
      setStage('hold');
    }, 800);

    // Start zoom out
    const zoomOutTimer = setTimeout(() => {
      setStage('zoom-out');
    }, 1800);

    // Complete animation
    const completeTimer = setTimeout(() => {
      onComplete();
    }, 2500);

    return () => {
      clearTimeout(holdTimer);
      clearTimeout(zoomOutTimer);
      clearTimeout(completeTimer);
    };
  }, [onComplete]);

  return (
    <div className="fixed inset-0 z-[100] bg-white dark:bg-slate-900 flex items-center justify-center overflow-hidden">
      {/* Animated background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-cyan-500/5 animate-pulse"></div>
      
      {/* Logo container with zoom animation */}
      <div
        className={`relative transition-all duration-700 ease-in-out ${
          stage === 'zoom-in'
            ? 'scale-0 opacity-0'
            : stage === 'hold'
            ? 'scale-100 opacity-100'
            : 'scale-[3] opacity-0'
        }`}
      >
        <img
          src={logo}
          alt="ShellKode"
          className="w-64 h-64 object-contain drop-shadow-2xl"
        />
        
        {/* Pulsing ring effect */}
        {stage === 'hold' && (
          <>
            <div className="absolute inset-0 rounded-full border-4 border-primary/30 animate-ping"></div>
            <div className="absolute inset-0 rounded-full border-2 border-primary/50 animate-pulse"></div>
          </>
        )}
      </div>

      {/* Loading text */}
      {stage === 'hold' && (
        <div className="absolute bottom-1/3 left-1/2 transform -translate-x-1/2 text-center animate-fade-in">
          <p className="text-xl font-semibold text-slate-700 dark:text-slate-300 mb-2">
            Analyzing Security Data
          </p>
          <div className="flex items-center justify-center gap-2">
            <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
            <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
            <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LoadingAnimation;
