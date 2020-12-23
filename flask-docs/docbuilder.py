import os
import re
import json
import shutil
import tempfile
import subprocess

import click


config_override_template = '''\
new_theme = %(new_theme)s

import os
import sys

if not new_theme:
    sys.path.insert(0, %(theme_path)r)
    #__import__('pocoo_theme_support')

sys.path[:] = [os.path.abspath(x) for x in sys.path]

# Some defaults
html_static_path = []
html_favicon = None
html_logo = None
latex_additional_files = []
latex_logo = None

# Source the old file and ensure the paths are setup correctly afterwards
_old_file = __file__
__file__ = 'conf.py'
_here = os.getcwd()
_real_path = %(real_path)r
os.chdir(_real_path)

with open('conf.py', 'rb') as f:
    code = compile(f.read(), 'conf.py', 'exec')
    exec(code, globals())

sys.path[:] = [os.path.abspath(x) for x in sys.path]
os.chdir(_here)


def fix_path(x):
    if x:
        return os.path.join(_real_path, x)


html_static_path = [fix_path(_x) for _x in html_static_path]
latex_additional_files = [fix_path(_x) for _x in latex_additional_files]
__file__ = _old_file

if not new_theme:
    html_additional_pages = dict(globals().get('html_additional_pages') or {})
    html_additional_pages['404'] = '404.html'

html_favicon = fix_path(html_favicon)
html_logo = fix_path(html_logo)
latex_logo = fix_path(latex_logo)

release = %(release)r
version = %(version)r

# Overrides
if not new_theme:
    html_favicon = None
    project = %(project)r

    templates_path = []
    html_title = '%%s Documentation (%%s)' %% (project, version)
    html_theme = %(theme)r
    html_theme_options = {}
    html_theme_path = [%(theme_path)r]
    html_sidebars = %(sidebars)r

    pygments_style = %(pygments_style)r

html_context = dict(globals().get('html_context') or {})
html_context.update(%(context_vars)r)
'''

build_script = '''\
#!/bin/bash
. %(venv_path)s/bin/activate

pip install --upgrade Sphinx

export PYTHONPATH="%(checkout_path)s:$PYTHONPATH"

cd %(checkout_path)s
pip install --editable .
git submodule update --init

%(build_steps)s

cd %(doc_source_path)s

sphinx-build \\
    -d %(doc_source_path)s/.doctrees \\
    -b dirhtml -c "%(config_path)s" -T . "%(output_path)s"

#sphinx-build \\
#    -d %(doc_source_path)s/.doctrees \\
#    -b json -c "%(config_path)s" -T . "%(output_path)s"

#sphinx-build \\
#    -d %(doc_source_path)s/.doctrees \\
#    -b latex -c "%(config_path)s" -T . "%(output_path)s/.latex"

#(cd %(output_path)s/.latex; make all-pdf)
'''


def build_context_vars(this_version, config):
    versions = []
    warning = None
    config_new_theme = config.get('new_theme')
    current_new_theme = None

    for version in config['versions']:
        is_current = this_version == version['slug']
        versions.append({
            'slug': version['slug'],
            'title': version['title'],
            'note': version.get('note'),
            'is_current': is_current,
        })
        if is_current:
            warning = version.get('warning')
            current_new_theme = version.get('new_theme')

    if config_new_theme or current_new_theme:
        return {
            'versions': versions,
        }

    return {
        'documentation_versions': versions,
        'documentation_version_warning': warning,
    }


def ensure_checkout(checkout_folder, repo_url):
    try:
        os.makedirs(checkout_folder)
    except OSError:
        pass

    client = None
    url, branch = repo_url.rsplit('@', 1)
    try:
        if os.path.isdir(os.path.join(checkout_folder, '.git')):
            client = subprocess.Popen([
                'git', 'fetch', 'origin',
                '%s:%s' % (branch, branch),
                '--update-head-ok',
            ], cwd=checkout_folder)
            client.wait()
            client = subprocess.Popen([
                'git', 'reset', '--hard',
            ], cwd=checkout_folder)
            client.wait()
            client = subprocess.Popen([
                'git', 'checkout', '--force', branch,
            ], cwd=checkout_folder)
            client.wait()
        else:
            client = subprocess.Popen([
                'git', 'clone',
                '--branch', branch,
                url,
                checkout_folder
            ])
            client.wait()
    finally:
        if client is not None:
            try:
                client.kill()
            except OSError:
                pass


def build_version(config, version_config, output_folder, checkout_folder):
    version_checkout_folder = os.path.abspath(os.path.join(
        checkout_folder, str('%s-%s' % (config['id'],
                                        version_config['slug']))))
    venv_path = os.path.join(version_checkout_folder, '.venv')

    ensure_checkout(version_checkout_folder, version_config['repo'])
    doc_source_path = os.path.join(version_checkout_folder,
                                   str(config['doc_path']))

    config_path = tempfile.mkdtemp(prefix='.versionoverlay')
    context_vars = build_context_vars(version_config['slug'], config)
    new_theme = bool(
        config.get('new_theme') or version_config.get('new_theme'))
    client = None

    try:
        if new_theme:
            client = subprocess.Popen(['python3.6', '-m', 'venv', venv_path])
        else:
            client = subprocess.Popen(['virtualenv', venv_path])
        client.wait()

        with open(os.path.join(config_path, 'conf.py'), 'w') as f:
            f.write(config_override_template % {
                'project': config['name'],
                'new_theme': new_theme,
                'version': '.'.join(version_config['version'].split('.')[:2]),
                'release': version_config['version'],
                'real_path': doc_source_path,
                'theme_path': config['theme_path'],
                'theme': config.get('theme') or 'pocoo',
                'pygments_style': config.get('pygments_style')
                    or 'pocoo_theme_support.PocooStyle',
                'sidebars': config.get('sidebars') or {},
                'context_vars': context_vars,
            } + '\n')

        build_script_path = os.path.join(config_path, 'build.sh')
        with open(build_script_path, 'w') as f:
            f.write(build_script % {
                'venv_path': venv_path,
                'checkout_path': version_checkout_folder,
                'doc_source_path': doc_source_path,
                'output_path': os.path.abspath(output_folder),
                'config_path': config_path,
                'build_steps': '\n'.join(config.get('pre_build_steps') or ()),
            })

        client = subprocess.Popen(['bash', build_script_path])
        client.wait()
    finally:
        if client is not None:
            try:
                client.kill()
            except OSError:
                pass
        try:
            shutil.rmtree(config_path)
        except (OSError, IOError):
            pass


def _load_config(filename):
    with open(filename) as f:
        cfg = json.load(f)
    cfg['base_path'] = os.path.abspath(os.path.dirname(filename))
    cfg['theme_path'] = os.path.join(
        cfg['base_path'], cfg.get('theme_path', './themes'))
    return cfg


def load_config(ctx, param, filename):
    try:
        return _load_config(filename)
    except IOError as e:
        raise click.BadParameter('Could not load config: %s' % e)


def iter_configs(folder):
    for filename in os.listdir(folder):
        if filename.endswith('.json'):
            yield _load_config(os.path.join(folder, filename))


def generate_nginx_config(config, path, url_prefix=None):
    if url_prefix is None:
        url_prefix = config.get('default_url_prefix', '/')
    url_prefix = url_prefix.rstrip('/')
    escaped_prefix = re.escape(url_prefix)

    try_versions = []
    for version in config['versions']:
        t = version.get('type')
        if t == 'stable':
            try_versions.append((0, version['slug']))
        elif t == 'unstable':
            try_versions.append((1, version['slug']))
    try_versions.sort()

    buf = []
    w = buf.append

    # Regular documentation versions.
    for version in config['versions']:
        w('location %s/%s {' % (url_prefix, version['slug']))
        w('  alias %s/%s;' % (path, version['slug']))
        w('}')
        w('')

    # Fallback blocks.  This also redirects the inventories.
    w('location %s {' % (url_prefix or '/'))
    w('  rewrite ^%s/?$ %s/latest/ redirect;' % (escaped_prefix, url_prefix))

    for redirect_prefix in '/latest', '':
        w('')
        # Always redirect the inventory to the development one for
        # intersphinx.
        w('  rewrite ^%s%s/objects.inv$ %s/%s/objects.inv;' %
          (escaped_prefix, redirect_prefix,
           url_prefix, try_versions[-1][1]))
        w('  set $doc_path XXX;')
        w('  if ($request_uri ~* "^%s%s(|/[^?]*?)$") {' %
          (escaped_prefix, redirect_prefix))
        w('    set $doc_path $1;')
        w('  }')
        for _, version in try_versions:
            w('')
            w('  if (-f %s/%s$doc_path/index.html) {' % (path, version))
            w('    return 302 %s/%s$doc_path;' % (url_prefix, version))
            w('  }')
    w('}')
    return '\n'.join(buf)


@click.group()
def cli():
    """A wrapper around sphinx-build."""


@cli.command()
@click.option('--config', type=click.Path(), required=True,
              callback=load_config,
              help='The path to the documentation config file.')
@click.option('--checkout-folder', type=click.Path(),
              default='checkouts')
@click.option('--output', '-O', type=click.Path(), default=None,
              help='The path to the output folder.')
def build(config, checkout_folder, output):
    """Builds all documentation."""
    if output is None:
        output = 'build/%s' % str(config['id'])

    for version_cfg in config['versions']:
        build_version(config, version_cfg,
                      os.path.join(output, str(version_cfg['slug'])),
                      checkout_folder)


@cli.command('nginx-config')
@click.option('--config', type=click.Path(), required=True,
              callback=load_config,
              help='The path to the documentation config file.')
@click.option('--url-prefix', default=None,
              help='The URL prefix for the documentation.')
@click.option('--path', type=click.Path(),
              help='The path to the documentation on the filesystem.')
def nginx_config(url_prefix, path, config):
    """Spits out an nginx config for the given project that is ready
    for inclusion.  This is useful because the docs have links to the
    latest version of the docs but it requires webserver interaction
    to support that pseudo URL.
    """
    if path is None:
        path = os.path.abspath('build/%s' % str(config['id']))

    click.echo(generate_nginx_config(config, path, url_prefix))


@cli.command('build-all')
@click.option('--config-folder', type=click.Path(), required=True,
              default='configs', help='The folder with the config files')
@click.option('--checkout-folder', type=click.Path(),
              default='checkouts')
@click.option('--build-folder', type=click.Path(), default='build',
              help='Where to place the built documentation.')
def build_all(config_folder, checkout_folder, build_folder):
    """Builds all the documentation and places it in a folder together
    with the nginx configs.
    """
    for config in iter_configs(config_folder):
        output = '%s/%s' % (build_folder, str(config['id']))
        for version_cfg in config['versions']:
            build_version(config, version_cfg,
                          os.path.join(output, str(version_cfg['slug'])),
                          checkout_folder)

        nginx_cfg = generate_nginx_config(config, os.path.abspath(output))
        with open(os.path.join(output, 'nginx.conf'), 'w') as f:
            f.write(nginx_cfg + '\n')
