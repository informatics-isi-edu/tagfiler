#!/usr/bin/env python

# ...

from setuptools import setup

setup(name='psoc',
      version='1.0',
      description='psoc makes tagfiler service',
      author='MISD',
      author_email='misd@isi.edu',
      url='https://confluence.misd.isi.edu:8443/display/PSOC/PSOC+Tagfiler+Data+Repository',
      long_description="For data sharing, PSOC is using a data repository developed at the USC/ISI Medical Information Systems Division (MISD).",
      license="University of Southern California",
      platforms=["CentOS 5.5"],
      install_requires=['httpd', 'mod_wsgi',
                        'postgresql', 'postgresql-devel', 'postgresql-server',  
                        'python', 'python-psycopg2', 'python-webpy', 'python-ply']
     )
