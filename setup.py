import setuptools

setuptools.setup(
    name='pyperf',
    version='0.0.1',
    install_requires=[
        'Click==7.0',
    ],
    packages=setuptools.find_packages(),
    entry_points='''
        [console_scripts]
        pyperf=pyperf:check
    ''',
    author="Reece Dunham",
    author_email="me@rdil.rocks"
)
