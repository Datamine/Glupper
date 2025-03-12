import { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import Feed from '../components/Feed';
import Head from 'next/head';
import api from '../utils/api';
import { useAuth } from '../contexts/AuthContext';

export default function Explore() {
  const { isAuthenticated } = useAuth();
  const [trendingTopics, setTrendingTopics] = useState([]);
  const [trendingPosts, setTrendingPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTrending = async () => {
      setLoading(true);
      
      try {
        // Fetch trending topics
        const topicsResponse = await api.get('/api/v1/feed/trending/topics');
        setTrendingTopics(topicsResponse.data || []);
        
        // Fetch trending posts
        const postsResponse = await api.get('/api/v1/feed/trending/posts');
        setTrendingPosts(postsResponse.data || []);
      } catch (error) {
        console.error('Error fetching trending data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchTrending();
  }, []);

  return (
    <Layout>
      <Head>
        <title>Explore | Glupper</title>
        <meta name="description" content="Explore trending topics and posts on Glupper" />
      </Head>

      <div style={{ 
        padding: '1rem', 
        borderBottom: '1px solid var(--light-color)',
        position: 'sticky',
        top: 0,
        backgroundColor: 'white',
        zIndex: 10
      }}>
        <h1 style={{ fontWeight: 'bold', fontSize: '1.25rem' }}>Explore</h1>
      </div>

      {/* Trending Topics */}
      <div style={{ 
        padding: '1rem', 
        borderBottom: '1px solid var(--light-color)',
        backgroundColor: 'var(--white-color)'
      }}>
        <h2 style={{ fontWeight: 'bold', marginBottom: '1rem' }}>Trending Topics</h2>
        
        {loading ? (
          <p style={{ color: 'var(--secondary-color)' }}>Loading trending topics...</p>
        ) : trendingTopics.length > 0 ? (
          <div>
            {trendingTopics.map((topic, index) => (
              <div 
                key={index}
                style={{ 
                  padding: '0.75rem 0', 
                  borderBottom: index < trendingTopics.length - 1 ? '1px solid var(--light-color)' : 'none' 
                }}
              >
                <div style={{ fontWeight: 'bold' }}>#{topic.name}</div>
                <div style={{ fontSize: '0.875rem', color: 'var(--secondary-color)' }}>
                  {topic.post_count} posts
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: 'var(--secondary-color)' }}>No trending topics at the moment</p>
        )}
      </div>

      {/* Explore Feed */}
      <div style={{ 
        padding: '1rem', 
        borderBottom: '1px solid var(--light-color)',
        backgroundColor: 'var(--white-color)'
      }}>
        <h2 style={{ fontWeight: 'bold' }}>Discover Posts</h2>
      </div>

      {isAuthenticated ? (
        <Feed 
          endpoint="/api/v1/feed/explore"
          onEmpty="No posts to discover at the moment. Check back later!"
        />
      ) : (
        <div style={{ 
          padding: '2rem', 
          textAlign: 'center',
          color: 'var(--secondary-color)'
        }}>
          Please log in to explore posts.
        </div>
      )}
    </Layout>
  );
}