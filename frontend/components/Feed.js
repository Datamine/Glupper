import { useState, useEffect } from 'react';
import api from '../utils/api';
import Post from './Post';

export default function Feed({ 
  feedType = 'chronological',
  endpoint = '/api/v1/feed/home',
  queryParams = {},
  onEmpty = 'No posts to show'
}) {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cursor, setCursor] = useState(null);
  const [hasMore, setHasMore] = useState(true);

  const loadPosts = async (reset = false) => {
    if (loading && !reset) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const params = {
        limit: 20,
        ...queryParams
      };
      
      // Add cursor for pagination if not resetting
      if (cursor && !reset) {
        params.cursor = cursor;
      }
      
      // Add feed type if endpoint is home feed
      if (endpoint === '/api/v1/feed/home') {
        params.feed_type = feedType;
      }
      
      const { data } = await api.get(endpoint, { params });
      
      if (reset) {
        setPosts(data.posts || []);
      } else {
        setPosts(prev => [...prev, ...(data.posts || [])]);
      }
      
      // Set cursor for next page if available
      if (data.next_cursor) {
        setCursor(data.next_cursor);
        setHasMore(true);
      } else {
        setHasMore(false);
      }
    } catch (err) {
      console.error('Error loading feed:', err);
      setError('Failed to load posts. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Reset and load posts when feedType changes
    setPosts([]);
    setCursor(null);
    setHasMore(true);
    loadPosts(true);
  }, [feedType, endpoint, JSON.stringify(queryParams)]);

  const handlePostUpdate = (updatedPost) => {
    setPosts(prevPosts => 
      prevPosts.map(post => 
        post.id === updatedPost.id ? updatedPost : post
      )
    );
  };

  const loadMore = () => {
    if (hasMore && !loading) {
      loadPosts();
    }
  };

  return (
    <div>
      {error && (
        <div style={{ 
          padding: '1rem', 
          backgroundColor: 'var(--danger-color)', 
          color: 'white',
          margin: '1rem',
          borderRadius: '4px'
        }}>
          {error}
        </div>
      )}
      
      {posts.length === 0 && !loading && !error ? (
        <div style={{ 
          padding: '2rem', 
          textAlign: 'center',
          color: 'var(--secondary-color)'
        }}>
          {onEmpty}
        </div>
      ) : (
        <div className="feed-container">
          {posts.map(post => (
            <Post 
              key={post.id} 
              post={post} 
              onPostUpdate={handlePostUpdate}
            />
          ))}
        </div>
      )}
      
      {loading && (
        <div style={{ 
          padding: '1rem', 
          textAlign: 'center',
          color: 'var(--secondary-color)'
        }}>
          Loading posts...
        </div>
      )}
      
      {hasMore && !loading && posts.length > 0 && (
        <div style={{ 
          padding: '1rem', 
          textAlign: 'center'
        }}>
          <button 
            className="btn btn-outline"
            onClick={loadMore}
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}