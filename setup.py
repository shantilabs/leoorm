from distutils.core import setup

from pip.req import parse_requirements


setup(
    name='leoorm',
    version='1.0',
    author='Maxim Oransky',
    author_email='maxim.oransky@gmail.com',
    packages=[
        'leoorm',
    ],
    url='https://github.com/shantilabs/leoorm',
    install_reqs=parse_requirements('requirements.txt')
)
