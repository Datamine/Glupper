import { useState } from 'react';
import api from '../utils/api';

export default function CommentForm({ postId, onCommentAdded }) {
  const [content, setContent] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Reset error
    setError('');
    
    // Validate content
    if (!content.trim()) {
      setError('Comment cannot be empty');
      return;
    }
    
    if (content.length > 300) {
      setError('Comment must be 300 characters or less');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const commentData = {
        content: content.trim(),
        media_urls: [] // Optional media URLs
      };
      
      const { data } = await api.post(`/api/v1/posts/${postId}/comments`, commentData);
      
      // Clear form and notify parent component
      setContent('');
      if (onCommentAdded) {
        onCommentAdded(data);
      }
    } catch (error) {
      console.error('Error posting comment:', error);
      setError(error.response?.data?.detail || 'Failed to post comment');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ 
      padding: '1rem', 
      borderBottom: '1px solid var(--light-color)',
      backgroundColor: 'var(--white-color)'
    }}>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <textarea
            className="form-input"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Add a comment..."
            maxLength={300}
            rows={3}
            style={{ resize: 'none' }}
          />
          <div style={{ 
            fontSize: '0.875rem', 
            color: 'var(--secondary-color)', 
            textAlign: 'right', 
            marginTop: '0.25rem' 
          }}>
            {content.length}/300
          </div>
        </div>
        
        {error && (
          <div style={{ color: 'var(--danger-color)', marginBottom: '1rem' }}>
            {error}
          </div>
        )}
        
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button 
            type="submit" 
            className="btn btn-primary"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Posting...' : 'Comment'}
          </button>
        </div>
      </form>
    </div>
  );
}