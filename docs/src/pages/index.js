import React from 'react';
import classnames from 'classnames';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from '../home/styles.module.css';

const features = [
  {
    title: <>Easy to Use</>,
    imageUrl: 'img/check.png',
    description: (
      <>
        PyPerf is designed to be easily installed and
        used to get your Python modules running faster.
      </>
    ),
  },
  {
    title: <>Focus on What Matters</>,
    imageUrl: 'img/python.svg',
    description: (
      <>
        Write code at your own pace, and
        we&apos;ll make it run at a great pace.
      </>
    ),
  },
  {
    title: <>Open Source</>,
    imageUrl: 'img/git.svg',
    description: (
      <>
        Extend, change, and help PyPerf by sending us a PR on GitHub! 
      </>
    ),
  },
];

function Feature({imageUrl, title, description}) {
  const imgUrl = useBaseUrl(imageUrl);
  return (
    <div className={classnames('col col--4', styles.feature)}>
      {imgUrl && (
        <div className="text--center">
          <img className={styles.featureImage} src={imgUrl} alt={title} width={200} height={200} />
        </div>
      )}
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

export default () => {
  const context = useDocusaurusContext();
  const {siteConfig = {}} = context;
  return (
    <Layout
      title={"PyPerf - The CLI that helps make your apps faster."}
      description="A CLI that checks for potential performance issues in your Python modules.">
      <header
        className={classnames('hero hero--primary', styles.heroBanner)}
      >
        <div className="container">
          <h1 className="hero__title">{siteConfig.title}</h1>
          <p className="hero__subtitle">{siteConfig.tagline}</p>
          <div className={styles.buttons}>
            <Link
              className={classnames(
                'button button--outline button--secondary button--lg',
                styles.getStarted,
              )}
              to={useBaseUrl('docs/intro')}
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>
      <main>
        {features && features.length && (
          <section className={styles.features}>
            <div className="container">
              <div className="row">
                {features.map((props, idx) => (
                  <Feature key={idx} {...props} />
                ))}
              </div>
            </div>
          </section>
        )}
      </main>
    </Layout>
  );
}
