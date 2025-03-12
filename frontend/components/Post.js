import { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { FaRegComment, FaRetweet, FaRegHeart, FaHeart, FaExternalLinkAlt } from 'react-icons/fa';
import api from '../utils/api';
import { useAuth } from '../contexts/AuthContext';

export default function Post({ post, showActions = true, onPostUpdate }) {
  const router = useRouter();
  const { user } = useAuth();
  const [liked, setLiked] = useState(post.liked_by_current_user || false);
  const [likesCount, setLikesCount] = useState(post.likes_count || 0);
  const [isLoading, setIsLoading] = useState(false);

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  const handleLike = async () => {
    if (isLoading) return;
    
    setIsLoading(true);
    
    try {
      if (!liked) {
        await api.post(`/api/v1/posts/${post.id}/like`);
        setLiked(true);
        setLikesCount(prevCount => prevCount + 1);
      } else {
        await api.post(`/api/v1/posts/${post.id}/unlike`);
        setLiked(false);
        setLikesCount(prevCount => Math.max(0, prevCount - 1));
      }
      
      if (onPostUpdate) {
        onPostUpdate({
          ...post,
          liked_by_current_user: !liked,
          likes_count: !liked ? likesCount + 1 : Math.max(0, likesCount - 1)
        });
      }
    } catch (error) {
      console.error('Error toggling like:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRepost = async () => {
    if (isLoading) return;
    
    setIsLoading(true);
    
    try {
      const { data } = await api.post(`/api/v1/posts/${post.id}/repost`);
      if (data) {
        router.push('/');
      }
    } catch (error) {
      console.error('Error reposting:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleComment = () => {
    router.push(`/post/${post.id}`);
  };

  const isOwnPost = user && post.user_id === user.id;

  return (
    <div className="feed-item" onClick={() => router.push(`/post/${post.id}`)}>
      {post.is_repost && post.original_post && (
        <div style={{ marginBottom: '0.5rem', fontSize: '0.875rem', color: 'var(--secondary-color)' }}>
          <FaRetweet style={{ marginRight: '0.5rem' }} />
          <Link 
            href={`/profile/${post.user_id}`}
            onClick={(e) => e.stopPropagation()}
          >
            {post.user.username} reposted
          </Link>
        </div>
      )}
      
      <div className="post-header">
        <Link 
          href={`/profile/${post.user_id}`} 
          onClick={(e) => e.stopPropagation()}
        >
          <img 
            src={post.user.profile_picture_url || '/default-avatar.png'} 
            alt={post.user.username} 
            className="post-avatar" 
          />
        </Link>
        
        <div>
          <Link 
            href={`/profile/${post.user_id}`}
            onClick={(e) => e.stopPropagation()}
            className="post-name"
          >
            {post.user.username}
          </Link>
          <span className="post-username">@{post.user.username}</span>
        </div>
        
        <span className="post-time">{formatDate(post.created_at)}</span>
      </div>
      
      <div className="post-content">
        <h3>{post.title}</h3>
        {post.url && (
          <a 
            href={post.url} 
            target="_blank" 
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{ display: 'flex', alignItems: 'center', marginTop: '0.5rem', color: 'var(--primary-color)' }}
          >
            {post.url}
            <FaExternalLinkAlt style={{ marginLeft: '0.5rem', fontSize: '0.875rem' }} />
          </a>
        )}
      </div>
      
      {showActions && (
        <div className="post-actions">
          <button 
            className="post-action" 
            onClick={(e) => {
              e.stopPropagation();
              handleComment();
            }}
          >
            <FaRegComment style={{ marginRight: '0.5rem' }} />
            {post.comments_count || 0}
          </button>
          
          {!isOwnPost && (
            <button 
              className="post-action" 
              onClick={(e) => {
                e.stopPropagation();
                handleRepost();
              }}
              disabled={isLoading}
            >
              <FaRetweet style={{ marginRight: '0.5rem' }} />
              {post.reposts_count || 0}
            </button>
          )}
          
          <button 
            className="post-action" 
            onClick={(e) => {
              e.stopPropagation();
              handleLike();
            }}
            disabled={isLoading}
            style={{ color: liked ? 'var(--danger-color)' : 'var(--secondary-color)' }}
          >
            {liked ? (
              <FaHeart style={{ marginRight: '0.5rem' }} />
            ) : (
              <FaRegHeart style={{ marginRight: '0.5rem' }} />
            )}
            {likesCount}
          </button>
        </div>
      )}
    </div>
  );
}