import { createContext, useState, useContext, useEffect } from 'react';
import api from '../utils/api';
import Cookies from 'js-cookie';
import { useRouter } from 'next/router';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Load user on initial render
  useEffect(() => {
    const loadUser = async () => {
      const token = Cookies.get('token');
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const { data } = await api.get('/auth/me');
        setUser(data);
      } catch (error) {
        Cookies.remove('token');
      } finally {
        setLoading(false);
      }
    };

    loadUser();
  }, []);

  // Register a new user
  const register = async (userData) => {
    const { data } = await api.post('/auth/register', userData);
    return data;
  };

  // Login user
  const login = async (credentials) => {
    const { data } = await api.post('/auth/login', credentials, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });
    
    Cookies.set('token', data.access_token, { expires: 7 });
    
    // Fetch user data
    const userData = await api.get('/auth/me');
    setUser(userData.data);
    
    return data;
  };

  // Logout user
  const logout = () => {
    Cookies.remove('token');
    setUser(null);
    router.push('/login');
  };

  // Update user profile
  const updateProfile = async (profileData) => {
    const { data } = await api.put('/api/v1/users/me', profileData);
    setUser({ ...user, ...data });
    return data;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        register,
        login,
        logout,
        updateProfile,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);