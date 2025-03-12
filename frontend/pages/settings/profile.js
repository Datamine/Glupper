import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import Head from 'next/head';
import api from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import { FaArrowLeft, FaSave } from 'react-icons/fa';

export default function ProfileSettings() {
  const router = useRouter();
  const { user, updateProfile, isAuthenticated } = useAuth();
  
  const [bio, setBio] = useState('');
  const [profilePictureUrl, setProfilePictureUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (user) {
      setBio(user.bio || '');
      setProfilePictureUrl(user.profile_picture_url || '');
    }
  }, [user]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Reset messages
    setError('');
    setSuccess('');
    
    setIsSubmitting(true);
    
    try {
      const profileData = {
        bio,
        profile_picture_url: profilePictureUrl
      };
      
      await updateProfile(profileData);
      setSuccess('Profile updated successfully');
    } catch (err) {
      console.error('Error updating profile:', err);
      setError(err.response?.data?.detail || 'Failed to update profile');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <Layout>
        <Head>
          <title>Edit Profile | Glupper</title>
          <meta name="description" content="Edit your Glupper profile" />
        </Head>
        
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          Please log in to edit your profile.
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <Head>
        <title>Edit Profile | Glupper</title>
        <meta name="description" content="Edit your Glupper profile" />
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
        <h1 style={{ fontWeight: 'bold', fontSize: '1.25rem' }}>Edit Profile</h1>
      </div>
      
      <div style={{ padding: '1rem' }}>
        <form onSubmit={handleSubmit}>
          {/* Current profile picture display */}
          <div style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
            <img 
              src={profilePictureUrl || '/default-avatar.png'} 
              alt={user?.username || 'Profile'} 
              style={{ 
                width: '100px', 
                height: '100px', 
                borderRadius: '50%',
                border: '3px solid var(--primary-color)',
                margin: '0 auto 1rem auto',
                display: 'block'
              }} 
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="profilePictureUrl" className="form-label">Profile Picture URL</label>
            <input
              id="profilePictureUrl"
              className="form-input"
              type="text"
              value={profilePictureUrl}
              onChange={(e) => setProfilePictureUrl(e.target.value)}
              placeholder="https://example.com/image.jpg"
            />
            <div style={{ fontSize: '0.875rem', color: 'var(--secondary-color)', marginTop: '0.25rem' }}>
              Enter a URL for your profile picture
            </div>
          </div>
          
          <div className="form-group">
            <label htmlFor="bio" className="form-label">Bio</label>
            <textarea
              id="bio"
              className="form-input"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="Tell us about yourself"
              rows={4}
              style={{ resize: 'vertical' }}
              maxLength={160}
            />
            <div style={{ fontSize: '0.875rem', color: 'var(--secondary-color)', textAlign: 'right', marginTop: '0.25rem' }}>
              {bio.length}/160
            </div>
          </div>
          
          {error && (
            <div style={{ 
              padding: '0.75rem', 
              backgroundColor: 'rgba(224, 36, 94, 0.1)', 
              color: 'var(--danger-color)',
              marginBottom: '1rem',
              borderRadius: '4px'
            }}>
              {error}
            </div>
          )}
          
          {success && (
            <div style={{ 
              padding: '0.75rem', 
              backgroundColor: 'rgba(23, 191, 99, 0.1)', 
              color: 'var(--success-color)',
              marginBottom: '1rem',
              borderRadius: '4px'
            }}>
              {success}
            </div>
          )}
          
          <button 
            type="submit" 
            className="btn btn-primary"
            disabled={isSubmitting}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <FaSave style={{ marginRight: '0.5rem' }} />
            {isSubmitting ? 'Saving...' : 'Save Profile'}
          </button>
        </form>
      </div>
    </Layout>
  );
}