import setuptools

setuptools.setup(
    name='Perf',
    version='0.0.1',
    install_requires=[
        'Click==7.0',
        'area4>=3.0.0',
        'pyflakes==2.1.1',
    ],
    packages=setuptools.find_packages(),
    entry_points='''
        [console_scripts]
        perf=perf:check
    ''',
    author="Reece Dunham",
    author_email="me@rdil.rocks",
    zip_safe=False,
    include_package_data=True,
    python_requires=">3.3"
)
