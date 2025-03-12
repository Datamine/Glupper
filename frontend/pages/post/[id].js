import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import Layout from '../../components/Layout';
import Post from '../../components/Post';
import CommentForm from '../../components/CommentForm';
import api from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import { FaArrowLeft } from 'react-icons/fa';

export default function PostDetail() {
  const router = useRouter();
  const { id } = router.query;
  const { isAuthenticated } = useAuth();
  
  const [post, setPost] = useState(null);
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!id) return;
    
    const fetchPost = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const { data } = await api.get(`/api/v1/posts/${id}`);
        
        setPost(data);
        setComments(data.comments || []);
      } catch (err) {
        console.error('Error fetching post:', err);
        setError('Failed to load post. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    
    fetchPost();
  }, [id]);

  const handleCommentAdded = (newComment) => {
    setComments(prevComments => [newComment, ...prevComments]);
  };

  const handlePostUpdate = (updatedPost) => {
    setPost(updatedPost);
  };

  return (
    <Layout>
      <Head>
        <title>{post ? `${post.title} | Glupper` : 'Post | Glupper'}</title>
        <meta name="description" content={post ? post.title : 'Post detail on Glupper'} />
      </Head>
      
      <div style={{ 
        padding: '1rem', 
        borderBottom: '1px solid var(--light-color)',
        position: 'sticky',
        top: 0,
        backgroundColor: 'white',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center'
      }}>
        <button 
          onClick={() => router.back()}
          style={{ 
            background: 'none', 
            border: 'none', 
            marginRight: '1rem',
            display: 'flex',
            alignItems: 'center',
            color: 'var(--primary-color)'
          }}
        >
          <FaArrowLeft />
        </button>
        <h1 style={{ fontWeight: 'bold', fontSize: '1.25rem' }}>Post</h1>
      </div>
      
      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          Loading post...
        </div>
      ) : error ? (
        <div style={{ 
          padding: '1rem', 
          backgroundColor: 'var(--danger-color)', 
          color: 'white',
          margin: '1rem',
          borderRadius: '4px'
        }}>
          {error}
        </div>
      ) : post ? (
        <div>
          {/* Main post */}
          <Post 
            post={post} 
            showActions={true}
            onPostUpdate={handlePostUpdate}
          />
          
          {/* Comment form */}
          {isAuthenticated && (
            <CommentForm 
              postId={post.id} 
              onCommentAdded={handleCommentAdded}
            />
          )}
          
          {/* Comments */}
          <div style={{ 
            borderBottom: '1px solid var(--light-color)',
            padding: '1rem',
            backgroundColor: 'var(--bg-color)'
          }}>
            <h2 style={{ fontWeight: 'bold' }}>Comments ({comments.length})</h2>
          </div>
          
          {comments.length === 0 ? (
            <div style={{ 
              padding: '2rem', 
              textAlign: 'center',
              color: 'var(--secondary-color)'
            }}>
              No comments yet. Be the first to comment!
            </div>
          ) : (
            <div>
              {comments.map(comment => (
                <Post 
                  key={comment.id} 
                  post={comment} 
                  showActions={true}
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          Post not found
        </div>
      )}
    </Layout>
  );
}