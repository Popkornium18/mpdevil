project('mpdevil', version: '1.5.1')

i18n = import('i18n')
gnome = import('gnome')

python = import('python').find_installation()
pylibdir = python.get_install_dir()

resources_dir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())

conf = configuration_data()
conf.set('RESOURCES_DIR', resources_dir)
conf.set('LOCALE_DIR', join_paths(get_option('prefix'), get_option('datadir'), 'locale'))

subdir('data')
subdir('po')

configure_file(
          input: 'constants.py.in',
         output: 'constants.py',
  configuration: conf,
    install_dir: join_paths(pylibdir, 'mpdevil')
)

configure_file(
          input: 'bin/mpdevil',
         output: 'mpdevil',
  configuration: conf,
    install_dir: join_paths(get_option('prefix'), get_option('bindir'))
)

install_subdir(
  'src/mpdevil',
  install_dir: pylibdir,
)
