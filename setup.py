from distutils.core import setup

setup(
    name='leoorm',
    version='1.2.1',
    author='Maxim Oransky',
    author_email='maxim.oransky@gmail.com',
    packages=[
        'leoorm',
    ],
    url='https://github.com/shantilabs/leoorm',
    install_requires=[
        'asyncpg>=0.15.0'
        'Django>=1.6',
    ],
)
