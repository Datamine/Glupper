import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <meta charSet="utf-8" />
        <meta name="theme-color" content="#1DA1F2" />
        <link rel="icon" href="/favicon.ico" />
        <meta name="description" content="Glupper - Share and discuss interesting content" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}