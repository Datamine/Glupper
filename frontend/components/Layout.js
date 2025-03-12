import { useRouter } from 'next/router';
import Link from 'next/link';
import { useAuth } from '../contexts/AuthContext';
import { FaHome, FaUser, FaSearch, FaBell, FaEnvelope, FaSignOutAlt } from 'react-icons/fa';

export default function Layout({ children }) {
  const { user, logout, isAuthenticated } = useAuth();
  const router = useRouter();

  // Don't show layout on auth pages
  if (router.pathname === '/login' || router.pathname === '/register') {
    return <>{children}</>;
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated && typeof window !== 'undefined') {
    router.push('/login');
    return null;
  }

  return (
    <div className="app-layout">
      {/* Left Sidebar */}
      <div className="sidebar-left" style={{ padding: '1rem', borderRight: '1px solid var(--light-color)' }}>
        <div style={{ position: 'sticky', top: '1rem' }}>
          <div style={{ marginBottom: '2rem' }}>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--primary-color)' }}>Glupper</h1>
          </div>
          
          <nav>
            <ul style={{ listStyle: 'none' }}>
              <li style={{ marginBottom: '1.5rem' }}>
                <Link href="/" style={{ display: 'flex', alignItems: 'center', fontSize: '1.25rem', fontWeight: 'bold' }}>
                  <FaHome style={{ marginRight: '0.75rem' }} /> Home
                </Link>
              </li>
              <li style={{ marginBottom: '1.5rem' }}>
                <Link href="/explore" style={{ display: 'flex', alignItems: 'center', fontSize: '1.25rem', fontWeight: 'bold' }}>
                  <FaSearch style={{ marginRight: '0.75rem' }} /> Explore
                </Link>
              </li>
              <li style={{ marginBottom: '1.5rem' }}>
                <Link href="/notifications" style={{ display: 'flex', alignItems: 'center', fontSize: '1.25rem', fontWeight: 'bold' }}>
                  <FaBell style={{ marginRight: '0.75rem' }} /> Notifications
                </Link>
              </li>
              <li style={{ marginBottom: '1.5rem' }}>
                <Link href="/messages" style={{ display: 'flex', alignItems: 'center', fontSize: '1.25rem', fontWeight: 'bold' }}>
                  <FaEnvelope style={{ marginRight: '0.75rem' }} /> Messages
                </Link>
              </li>
              <li style={{ marginBottom: '1.5rem' }}>
                <Link href={`/profile/${user?.id}`} style={{ display: 'flex', alignItems: 'center', fontSize: '1.25rem', fontWeight: 'bold' }}>
                  <FaUser style={{ marginRight: '0.75rem' }} /> Profile
                </Link>
              </li>
            </ul>
          </nav>
          
          <button 
            className="btn btn-primary btn-block"
            style={{ marginTop: '1rem' }}
            onClick={() => router.push('/compose')}
          >
            Post
          </button>
          
          {user && (
            <div style={{ marginTop: '2rem' }}>
              <button 
                onClick={logout}
                style={{ display: 'flex', alignItems: 'center', background: 'none', border: 'none', color: 'var(--secondary-color)' }}
              >
                <FaSignOutAlt style={{ marginRight: '0.5rem' }} /> Logout
              </button>
            </div>
          )}
        </div>
      </div>
      
      {/* Main Content */}
      <main style={{ borderRight: '1px solid var(--light-color)' }}>
        {children}
      </main>
      
      {/* Right Sidebar */}
      <div className="sidebar-right" style={{ padding: '1rem' }}>
        <div style={{ position: 'sticky', top: '1rem' }}>
          <div style={{ backgroundColor: 'var(--white-color)', borderRadius: '15px', padding: '1rem', marginBottom: '1rem' }}>
            <h2 style={{ marginBottom: '0.75rem', fontWeight: 'bold' }}>Trending Topics</h2>
            <div>
              {/* Will be populated by API call */}
              <p style={{ color: 'var(--secondary-color)' }}>Loading trending topics...</p>
            </div>
          </div>
          
          <div style={{ backgroundColor: 'var(--white-color)', borderRadius: '15px', padding: '1rem' }}>
            <h2 style={{ marginBottom: '0.75rem', fontWeight: 'bold' }}>Who to follow</h2>
            <div>
              {/* Will be populated by API call */}
              <p style={{ color: 'var(--secondary-color)' }}>Loading suggestions...</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}