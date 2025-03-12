import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import Head from 'next/head';
import Link from 'next/link';
import api from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import { FaEnvelope, FaEnvelopeOpen } from 'react-icons/fa';

export default function Messages() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const { data } = await api.get('/api/v1/messages/conversations');
        setConversations(data.conversations || []);
      } catch (err) {
        console.error('Error fetching conversations:', err);
        setError('Failed to load conversations. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    
    if (isAuthenticated) {
      fetchConversations();
    }
  }, [isAuthenticated]);

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    
    // If today, show time
    if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    }
    // If yesterday, show 'Yesterday'
    else if (date.toDateString() === yesterday.toDateString()) {
      return 'Yesterday';
    }
    // Otherwise show date
    else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
  };

  if (!isAuthenticated) {
    return (
      <Layout>
        <Head>
          <title>Messages | Glupper</title>
          <meta name="description" content="Your direct messages on Glupper" />
        </Head>
        
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          Please log in to view your messages.
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <Head>
        <title>Messages | Glupper</title>
        <meta name="description" content="Your direct messages on Glupper" />
      </Head>
      
      <div style={{ 
        padding: '1rem', 
        borderBottom: '1px solid var(--light-color)',
        position: 'sticky',
        top: 0,
        backgroundColor: 'white',
        zIndex: 10,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h1 style={{ fontWeight: 'bold', fontSize: '1.25rem' }}>Messages</h1>
        
        <button 
          className="btn btn-primary"
          onClick={() => router.push('/messages/new')}
          style={{ padding: '0.5rem 1rem' }}
        >
          New Message
        </button>
      </div>
      
      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          Loading conversations...
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
      ) : conversations.length === 0 ? (
        <div style={{ 
          padding: '2rem', 
          textAlign: 'center',
          color: 'var(--secondary-color)'
        }}>
          No messages yet. Start a conversation!
        </div>
      ) : (
        <div>
          {conversations.map(conversation => (
            <Link 
              key={conversation.user.id}
              href={`/messages/${conversation.user.id}`}
              style={{ textDecoration: 'none', color: 'inherit' }}
            >
              <div style={{ 
                padding: '1rem',
                borderBottom: '1px solid var(--light-color)',
                backgroundColor: conversation.unread_count > 0 ? 'rgba(29, 161, 242, 0.1)' : 'var(--white-color)',
                display: 'flex',
                alignItems: 'center'
              }}>
                <div style={{ marginRight: '1rem' }}>
                  <img 
                    src={conversation.user.profile_picture_url || '/default-avatar.png'} 
                    alt={conversation.user.username} 
                    style={{ 
                      width: '50px', 
                      height: '50px', 
                      borderRadius: '50%' 
                    }} 
                  />
                </div>
                
                <div style={{ flex: 1 }}>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between',
                    marginBottom: '0.25rem'
                  }}>
                    <div style={{ fontWeight: 'bold' }}>
                      {conversation.user.username}
                    </div>
                    <div style={{ 
                      fontSize: '0.875rem',
                      color: 'var(--secondary-color)'
                    }}>
                      {formatDate(conversation.last_message_time)}
                    </div>
                  </div>
                  
                  <div style={{ 
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem'
                  }}>
                    {conversation.unread_count > 0 ? (
                      <FaEnvelope size={14} color="var(--primary-color)" />
                    ) : (
                      <FaEnvelopeOpen size={14} color="var(--secondary-color)" />
                    )}
                    
                    <div style={{ 
                      fontSize: '0.875rem',
                      color: conversation.unread_count > 0 ? 'var(--dark-color)' : 'var(--secondary-color)',
                      fontWeight: conversation.unread_count > 0 ? 'bold' : 'normal',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      maxWidth: '250px'
                    }}>
                      {conversation.last_message_preview}
                    </div>
                    
                    {conversation.unread_count > 0 && (
                      <div style={{ 
                        backgroundColor: 'var(--primary-color)',
                        color: 'white',
                        borderRadius: '50%',
                        width: '20px',
                        height: '20px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.75rem',
                        marginLeft: 'auto'
                      }}>
                        {conversation.unread_count}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </Layout>
  );
}