import { useState } from 'react';
import Layout from '../components/Layout';
import Feed from '../components/Feed';
import Head from 'next/head';
import { useAuth } from '../contexts/AuthContext';

export default function Home() {
  const { isAuthenticated, loading } = useAuth();
  const [feedType, setFeedType] = useState('chronological');

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <Layout>
      <Head>
        <title>Home | Glupper</title>
        <meta name="description" content="Your Glupper home feed" />
      </Head>

      <div style={{ 
        padding: '1rem', 
        borderBottom: '1px solid var(--light-color)',
        position: 'sticky',
        top: 0,
        backgroundColor: 'white',
        zIndex: 10
      }}>
        <h1 style={{ fontWeight: 'bold', fontSize: '1.25rem' }}>Home</h1>
        
        <div style={{ marginTop: '1rem', display: 'flex', borderBottom: '1px solid var(--light-color)' }}>
          <button 
            onClick={() => setFeedType('chronological')}
            style={{ 
              padding: '0.75rem', 
              flex: 1,
              fontWeight: feedType === 'chronological' ? 'bold' : 'normal',
              color: feedType === 'chronological' ? 'var(--primary-color)' : 'var(--secondary-color)',
              borderBottom: feedType === 'chronological' ? '2px solid var(--primary-color)' : 'none',
              background: 'none',
              border: 'none'
            }}
          >
            Latest
          </button>
          <button 
            onClick={() => setFeedType('for_you')}
            style={{ 
              padding: '0.75rem', 
              flex: 1,
              fontWeight: feedType === 'for_you' ? 'bold' : 'normal',
              color: feedType === 'for_you' ? 'var(--primary-color)' : 'var(--secondary-color)',
              borderBottom: feedType === 'for_you' ? '2px solid var(--primary-color)' : 'none',
              background: 'none',
              border: 'none'
            }}
          >
            For You
          </button>
        </div>
      </div>

      {isAuthenticated ? (
        <Feed 
          feedType={feedType} 
          endpoint="/api/v1/feed/home"
          onEmpty="Your feed is empty. Follow some users to see their posts!"
        />
      ) : (
        <div style={{ 
          padding: '2rem', 
          textAlign: 'center',
          color: 'var(--secondary-color)'
        }}>
          Please log in to view your feed.
        </div>
      )}
    </Layout>
  );
}