import { create } from 'zustand';

const useAuthStore = create((set) => ({
  token: localStorage.getItem('cricviz_token') || null,
  setToken: (token) => {
    if (token) {
      localStorage.setItem('cricviz_token', token);
    } else {
      localStorage.removeItem('cricviz_token');
    }
    set({ token });
  },
  logout: () => {
    localStorage.removeItem('cricviz_token');
    set({ token: null });
  }
}));

export default useAuthStore;
