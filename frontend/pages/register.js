import { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Head from 'next/head';
import { useAuth } from '../contexts/AuthContext';

export default function Register() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [bio, setBio] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const router = useRouter();
  const { register, login } = useAuth();

  const validateEmail = (email) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Reset error
    setError('');
    
    // Validate inputs
    if (!username || !email || !password || !confirmPassword) {
      setError('All fields are required');
      return;
    }
    
    if (!validateEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }
    
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    
    if (password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }
    
    setIsLoading(true);
    
    try {
      // Register the user
      await register({
        username,
        email,
        password,
        bio: bio || undefined,
      });
      
      // Automatically log in the user
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);
      
      await login(formData);
      
      // Redirect to home page on successful registration and login
      router.push('/');
    } catch (error) {
      console.error('Registration error:', error);
      setError(error.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-form-container">
      <Head>
        <title>Register | Glupper</title>
        <meta name="description" content="Create a new Glupper account" />
      </Head>
      
      <div style={{ marginBottom: '2rem', textAlign: 'center' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--primary-color)' }}>Glupper</h1>
      </div>
      
      <div className="auth-form">
        <h2 style={{ marginBottom: '1.5rem', fontSize: '1.5rem', fontWeight: 'bold', textAlign: 'center' }}>Create your account</h2>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username" className="form-label">Username</label>
            <input
              id="username"
              className="form-input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Choose a username"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="email" className="form-label">Email</label>
            <input
              id="email"
              className="form-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
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
              placeholder="Create a password"
              minLength={8}
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="confirmPassword" className="form-label">Confirm Password</label>
            <input
              id="confirmPassword"
              className="form-input"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm your password"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="bio" className="form-label">Bio (optional)</label>
            <textarea
              id="bio"
              className="form-input"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="Tell us about yourself"
              rows={3}
              style={{ resize: 'vertical' }}
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
            {isLoading ? 'Creating account...' : 'Sign up'}
          </button>
        </form>
        
        <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
          Already have an account?{' '}
          <Link href="/login">
            Log in
          </Link>
        </div>
      </div>
    </div>
  );
}