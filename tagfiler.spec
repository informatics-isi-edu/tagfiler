%define name tagfiler
%define version 1.0
%define unmangled_version 1.0
%define unmangled_version 1.0
%define release 1

Summary: service of a tag catalog
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{unmangled_version}.tar.gz
License: University of Southern California
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: MISD <misd@isi.edu>
Url: https://confluence.misd.isi.edu:8443/display/PSOC/PSOC+Tagfiler+Data+Repository

%description
For data sharing, tagfiler is using a data repository developed at the USC/ISI Medical Information Systems Division (MISD).

%prep
%setup -n %{name}-%{unmangled_version} -n %{name}-%{unmangled_version}

%build
python setup.py build

%install
python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%post
TAGFILERDIR=$(python -c 'import distutils.sysconfig;print distutils.sysconfig.get_python_lib()')/%{name}
%{__chmod} +x ${TAGFILERDIR}/tagfiler ${TAGFILERDIR}/tagfiler-httpd 
mv -R ${TAGFILERDIR}/templates /usr/share/tagfiler/
mv -R ${TAGFILERDIR}/dataserv.wsgi /usr/share/tagfiler/
mv ${TAGFILERDIR}/tagfiler /usr/sbin/
mv ${TAGFILERDIR}/tagfiler-httpd /usr/sbin/

if ! test -e /root/.deploytagfiler
	tagfiler-httpd
	touch /.deploytagfiler
fi


%files -f INSTALLED_FILES
%defattr(-,root,root)
