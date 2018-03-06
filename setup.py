from distutils.core import setup

from Cython.Build import cythonize
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
    ext_modules=cythonize('leoorm/core.pyx'),
    install_reqs=parse_requirements('requirements.txt')
)
