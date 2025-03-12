import Layout from '../components/Layout';
import PostForm from '../components/PostForm';
import Head from 'next/head';

export default function Compose() {
  return (
    <Layout>
      <Head>
        <title>New Post | Glupper</title>
        <meta name="description" content="Create a new post on Glupper" />
      </Head>
      
      <div style={{ 
        padding: '1rem', 
        borderBottom: '1px solid var(--light-color)',
        position: 'sticky',
        top: 0,
        backgroundColor: 'white',
        zIndex: 10
      }}>
        <h1 style={{ fontWeight: 'bold', fontSize: '1.25rem' }}>Create Post</h1>
      </div>
      
      <PostForm />
    </Layout>
  );
}