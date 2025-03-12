import { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Head from 'next/head';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const router = useRouter();
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Reset error
    setError('');
    
    // Validate inputs
    if (!username || !password) {
      setError('Please enter both username and password');
      return;
    }
    
    setIsLoading(true);
    
    try {
      // Format the data according to OAuth2 password flow
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);
      
      await login(formData);
      
      // Redirect to home page on successful login
      router.push('/');
    } catch (error) {
      console.error('Login error:', error);
      setError(error.response?.data?.detail || 'Invalid username or password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-form-container">
      <Head>
        <title>Login | Glupper</title>
        <meta name="description" content="Login to your Glupper account" />
      </Head>
      
      <div style={{ marginBottom: '2rem', textAlign: 'center' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--primary-color)' }}>Glupper</h1>
      </div>
      
      <div className="auth-form">
        <h2 style={{ marginBottom: '1.5rem', fontSize: '1.5rem', fontWeight: 'bold', textAlign: 'center' }}>Log in to Glupper</h2>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username" className="form-label">Username</label>
            <input
              id="username"
              className="form-input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password" className="form-label">Password</label>
            <input
              id="password"
              className="form-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
            />
          </div>
          
          {error && (
            <div style={{ color: 'var(--danger-color)', marginBottom: '1rem' }}>
              {error}
            </div>
          )}
          
          <button 
            type="submit" 
            className="btn btn-primary btn-block"
            disabled={isLoading}
          >
            {isLoading ? 'Logging in...' : 'Log in'}
          </button>
        </form>
        
        <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
          Don't have an account?{' '}
          <Link href="/register">
            Sign up
          </Link>
        </div>
      </div>
    </div>
  );
}