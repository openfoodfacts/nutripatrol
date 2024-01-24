# Nutripatrol

Open Food Facts moderation tool (WIP).

### Pre-Commit
This repo uses [pre-commit](https://pre-commit.com/) to enforce code styling, etc. To use it:
```console
pre-commit run
```
### How to install Nutripatrol ?

```
#! Clone and build locally
git clone https://github.com/openfoodfacts/nutripatrol.git
cd nutripatrol
docker-compose build
docker-compose up -d

#! Install dependencies from requirements.txt
pip install -r requirements.txt --no-index --find-links file:///tmp/packages

#! Launch vite environnement
npm install
npm run dev
```

Congrats ! You can now go to :
http://localhost:5173
and
http://localhost:8000/docs