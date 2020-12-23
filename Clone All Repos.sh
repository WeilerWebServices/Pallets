curl "https://api.github.com/orgs/pallets/repos?per_page=1000" | grep -o 'git@[^"]*' | xargs -L1 git clone

git clone https://github.com/pallets/flask.git
git clone https://github.com/pallets/flask-sphinx-themes.git
git clone https://github.com/pallets/flask-sqlalchemy.git
git clone https://github.com/pallets/markupsafe.git
git clone https://github.com/pallets/jinja.git
git clone https://github.com/pallets/werkzeug.git
git clone https://github.com/pallets/itsdangerous.git
git clone https://github.com/pallets/flask-website.git
git clone https://github.com/pallets/click.git
git clone https://github.com/pallets/flask-docs.git
git clone https://github.com/pallets/flask-ext-migrate.git
git clone https://github.com/pallets/pallets-sphinx-themes.git
git clone https://github.com/pallets/website.git
git clone https://github.com/pallets/meta.git
git clone https://github.com/pallets/cachelib.git
git clone https://github.com/pallets/secure-cookie.git
git clone https://github.com/pallets/.github.git
