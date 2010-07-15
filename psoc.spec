%define name psoc
%define version 1.0
%define unmangled_version 1.0
%define unmangled_version 1.0
%define release 1

Summary: psoc makes tagfiler service
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
For data sharing, PSOC is using a data repository developed at the USC/ISI Medical Information Systems Division (MISD).

%prep
%setup -n %{name}-%{unmangled_version} -n %{name}-%{unmangled_version}

%build
python setup.py build

%install
python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%post
PSOCDIR=$(python -c 'import distutils.sysconfig;print distutils.sysconfig.get_python_lib()')/%{name}
export SVCDIR=/var/www
%{__chmod} +x ${PSOCDIR}/*.sh
${PSOCDIR}/postinstall.sh tagfiler


%files -f INSTALLED_FILES
%defattr(-,root,root)
