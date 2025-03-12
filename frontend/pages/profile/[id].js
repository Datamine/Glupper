import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import Layout from '../../components/Layout';
import Feed from '../../components/Feed';
import api from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import { FaArrowLeft, FaUserEdit } from 'react-icons/fa';

export default function Profile() {
  const router = useRouter();
  const { id } = router.query;
  const { user, isAuthenticated } = useAuth();
  
  const [profile, setProfile] = useState(null);
  const [isFollowing, setIsFollowing] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('posts');

  const isOwnProfile = isAuthenticated && user && profile && user.id === profile.id;

  useEffect(() => {
    if (!id) return;
    
    const fetchProfile = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const { data } = await api.get(`/api/v1/users/${id}`);
        setProfile(data);
        
        // Check if the current user is following this profile
        if (isAuthenticated) {
          try {
            const followStatus = await api.get(`/api/v1/users/${id}/following/status`);
            setIsFollowing(followStatus.data.is_following);
          } catch (err) {
            console.error('Error checking follow status:', err);
          }
          
          // Check if the current user has muted this profile
          try {
            const muteStatus = await api.get(`/api/v1/users/${id}/muted`);
            setIsMuted(muteStatus.data.is_muted);
          } catch (err) {
            console.error('Error checking mute status:', err);
          }
        }
      } catch (err) {
        console.error('Error fetching profile:', err);
        setError('Failed to load profile. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    
    fetchProfile();
  }, [id, isAuthenticated]);

  const handleFollow = async () => {
    try {
      if (isFollowing) {
        await api.post(`/api/v1/users/${id}/unfollow`);
        setIsFollowing(false);
      } else {
        await api.post(`/api/v1/users/${id}/follow`);
        setIsFollowing(true);
      }
      
      // Update follower count in profile
      setProfile(prev => ({
        ...prev,
        followers_count: isFollowing ? 
          Math.max(0, prev.followers_count - 1) : 
          prev.followers_count + 1
      }));
    } catch (err) {
      console.error('Error toggling follow:', err);
    }
  };

  const handleMute = async () => {
    try {
      if (isMuted) {
        await api.post(`/api/v1/users/${id}/unmute`);
        setIsMuted(false);
      } else {
        await api.post(`/api/v1/users/${id}/mute`);
        setIsMuted(true);
      }
    } catch (err) {
      console.error('Error toggling mute:', err);
    }
  };

  return (
    <Layout>
      <Head>
        <title>{profile ? `${profile.username} | Glupper` : 'Profile | Glupper'}</title>
        <meta name="description" content={profile ? `${profile.username}'s profile on Glupper` : 'User profile on Glupper'} />
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
        <h1 style={{ fontWeight: 'bold', fontSize: '1.25rem' }}>
          {profile ? profile.username : 'Profile'}
        </h1>
      </div>
      
      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          Loading profile...
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
      ) : profile ? (
        <div>
          {/* Profile header */}
          <div className="profile-header">
            <div className="profile-banner"></div>
            
            <div className="profile-content">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <img 
                  src={profile.profile_picture_url || '/default-avatar.png'} 
                  alt={profile.username} 
                  className="profile-avatar"
                />
                
                {isAuthenticated && !isOwnProfile && (
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button 
                      className={`btn ${isFollowing ? 'btn-outline' : 'btn-primary'}`}
                      onClick={handleFollow}
                    >
                      {isFollowing ? 'Unfollow' : 'Follow'}
                    </button>
                    
                    <button 
                      className="btn btn-outline"
                      onClick={handleMute}
                      style={{ color: isMuted ? 'var(--danger-color)' : 'var(--secondary-color)' }}
                    >
                      {isMuted ? 'Unmute' : 'Mute'}
                    </button>
                  </div>
                )}
                
                {isOwnProfile && (
                  <button 
                    className="btn btn-outline"
                    onClick={() => router.push('/settings/profile')}
                  >
                    <FaUserEdit style={{ marginRight: '0.5rem' }} />
                    Edit Profile
                  </button>
                )}
              </div>
              
              <h2 className="profile-name">{profile.username}</h2>
              <div className="profile-username">@{profile.username}</div>
              
              {profile.bio && (
                <p className="profile-bio">{profile.bio}</p>
              )}
              
              <div className="profile-stats">
                <div className="profile-stat">
                  <span className="profile-stat-value">{profile.following_count}</span> Following
                </div>
                <div className="profile-stat">
                  <span className="profile-stat-value">{profile.followers_count}</span> Followers
                </div>
              </div>
            </div>
          </div>
          
          {/* Profile tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--light-color)' }}>
            <button 
              onClick={() => setActiveTab('posts')}
              style={{ 
                padding: '1rem', 
                flex: 1,
                fontWeight: activeTab === 'posts' ? 'bold' : 'normal',
                color: activeTab === 'posts' ? 'var(--primary-color)' : 'var(--secondary-color)',
                borderBottom: activeTab === 'posts' ? '2px solid var(--primary-color)' : 'none',
                background: 'none',
                border: 'none'
              }}
            >
              Posts
            </button>
            <button 
              onClick={() => setActiveTab('likes')}
              style={{ 
                padding: '1rem', 
                flex: 1,
                fontWeight: activeTab === 'likes' ? 'bold' : 'normal',
                color: activeTab === 'likes' ? 'var(--primary-color)' : 'var(--secondary-color)',
                borderBottom: activeTab === 'likes' ? '2px solid var(--primary-color)' : 'none',
                background: 'none',
                border: 'none'
              }}
            >
              Likes
            </button>
          </div>
          
          {/* Feed based on active tab */}
          {activeTab === 'posts' && (
            <Feed 
              endpoint={`/api/v1/posts/user/${profile.id}`}
              onEmpty="This user hasn't posted anything yet."
            />
          )}
          
          {activeTab === 'likes' && (
            <Feed 
              endpoint="/api/v1/posts/likes"
              onEmpty="This user hasn't liked any posts yet."
            />
          )}
        </div>
      ) : (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          User not found
        </div>
      )}
    </Layout>
  );
}