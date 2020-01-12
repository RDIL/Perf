module.exports = {
  title: 'PyPerf',
  tagline: 'A CLI that checks for potential performance issues in your Python modules.',
  url: 'https://pyperf.rdil.rocks',
  baseUrl: '/',
  favicon: 'img/favicon.ico',
  organizationName: 'RDIL',
  projectName: 'PyPerf',
  themeConfig: {
    navbar: {
      title: 'PyPerf',
      logo: {
        alt: 'PyPerf Logo',
        src: 'img/logo.svg'
      },
      links: [
        {to: 'docs/intro', label: 'Docs', position: 'left'},
        {
          href: 'https://github.com/RDIL/PyPerf',
          label: 'GitHub',
          position: 'right',
        }
      ]
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Social',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/RDIL/PyPerf',
            },
            {
              label: 'Twitter',
              href: 'https://twitter.com/rdil_pickle',
            },
            {
              label: 'GitHub Issues',
              href: 'https://github.com/RDIL/PyPerf/issues',
            }
          ]
        }
      ],
      copyright: `Copyright © 2020-present year, Reece Dunham.`
    }
  },
  presets: [
    [
      '@docusaurus/preset-classic',
      {
        docs: {
          sidebarPath: require.resolve('./sidebar.js'),
          editUrl: 'https://github.com/RDIL/PyPerf/edit/master/docs/',
          showLastUpdateAuthor: true,
          showLastUpdateTime: true
        },
        theme: {
          customCss: require.resolve('./src/home/banner.css'),
        }
      }
    ]
  ],
  plugins: [
    '@docusaurus/plugin-sitemap',
    {
      cacheTime: 600 * 1000,
      changefreq: 'daily',
      priority: 0.5,
    },
  ]
}
