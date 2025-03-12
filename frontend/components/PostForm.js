import { useState } from 'react';
import { useRouter } from 'next/router';
import api from '../utils/api';

export default function PostForm() {
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const router = useRouter();

  const validateUrl = (url) => {
    if (!url) return true; // URL is optional
    return url.startsWith('http://') || url.startsWith('https://');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Reset error
    setError('');
    
    // Validate inputs
    if (!title.trim()) {
      setError('Title is required');
      return;
    }
    
    if (title.length > 100) {
      setError('Title must be 100 characters or less');
      return;
    }
    
    if (!validateUrl(url)) {
      setError('URL must start with http:// or https://');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const postData = {
        title: title.trim(),
        url: url.trim() || null
      };
      
      await api.post('/api/v1/posts', postData);
      
      // Redirect to home page after successful post
      router.push('/');
    } catch (error) {
      console.error('Error creating post:', error);
      setError(error.response?.data?.detail || 'Failed to create post');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h2 style={{ marginBottom: '1rem', fontWeight: 'bold' }}>Create a Post</h2>
      
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="title" className="form-label">Title</label>
          <input
            id="title"
            className="form-input"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="What's on your mind?"
            maxLength={100}
          />
          <div style={{ fontSize: '0.875rem', color: 'var(--secondary-color)', textAlign: 'right', marginTop: '0.25rem' }}>
            {title.length}/100
          </div>
        </div>
        
        <div className="form-group">
          <label htmlFor="url" className="form-label">URL (optional)</label>
          <input
            id="url"
            className="form-input"
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com"
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
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Posting...' : 'Post'}
        </button>
      </form>
    </div>
  );
}