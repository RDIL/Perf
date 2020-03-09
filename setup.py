import setuptools

setuptools.setup(
    name='analyze-perf',
    version='0.1.0',
    description="CLI tool to analyze Python files for performance issues!",
    install_requires=[
        'Click==7.1',
        'area4>=3.0.0',
    ],
    packages=setuptools.find_packages(),
    entry_points='''
        [console_scripts]
        analyze-perf=perf:check
    ''',
    author="Reece Dunham",
    author_email="me@rdil.rocks",
    zip_safe=False,
    include_package_data=True,
    python_requires=">3.3",
    long_description=open("README.md", "r").read(),
    long_description_content_type="text/markdown",
    keywords="python performance cli tool perf analysis static"
)
