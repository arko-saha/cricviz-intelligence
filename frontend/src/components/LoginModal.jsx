import React, { useState } from 'react';
import useAuthStore from '../store/authStore';
import { login, register } from '../api/client';

const LoginModal = ({ isOpen, onClose }) => {
  const { setToken } = useAuthStore();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        await register(username, password);
        // Automatically login after register
        const data = await login(username, password);
        setToken(data.access_token);
        onClose();
      } else {
        const data = await login(username, password);
        setToken(data.access_token);
        onClose();
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#1e2330] p-6 rounded-xl border border-[#2a3040] w-full max-w-sm shadow-2xl">
        <h2 className="text-2xl font-bold text-white mb-4">
          {isRegister ? 'Create Account' : 'Analyst Login'}
        </h2>
        <p className="text-[#a0aabf] text-sm mb-6">
          You need to be logged in to access state-modifying actions like Data Ingestion or AI Analysis.
        </p>
        
        {error && (
          <div className="bg-red-500/20 border border-red-500/50 text-red-300 px-3 py-2 rounded-md mb-4 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-[#a0aabf] font-semibold mb-1">Username</label>
            <input 
              type="text" 
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              className="w-full bg-[#151922] border border-[#2a3040] text-white px-3 py-2 rounded-md focus:outline-none focus:border-[#00e6cc] transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-[#a0aabf] font-semibold mb-1">Password</label>
            <input 
              type="password" 
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="w-full bg-[#151922] border border-[#2a3040] text-white px-3 py-2 rounded-md focus:outline-none focus:border-[#00e6cc] transition-colors"
            />
          </div>
          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-gradient-to-r from-[#00e6cc] to-[#00b3a0] text-[#0a0d14] font-bold py-2 rounded-md mt-2 hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {loading ? 'Processing...' : (isRegister ? 'Register & Login' : 'Login')}
          </button>
        </form>

        <div className="mt-4 flex items-center justify-between text-sm">
          <button 
            onClick={() => { setIsRegister(!isRegister); setError(null); }}
            className="text-[#a0aabf] hover:text-white transition-colors"
          >
            {isRegister ? 'Already have an account? Login' : 'Need an account? Register'}
          </button>
          <button 
            onClick={onClose}
            className="text-[#a0aabf] hover:text-white transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

export default LoginModal;
