# Nutripatrol

Open Food Facts moderation tool (WIP).

### Wikipage 
- https://wiki.openfoodfacts.org/Moderation
- [Meeting minutes](https://docs.google.com/document/d/1B9Ci42kl_jrFt2hi3PiWW9tM9l6B1sI5kQMI9Zd6QS4/edit)

### Meeting
Valentin and Raphael are working on this tool. They meet weekly. Please ping them on Slack if you'd like to contribute. 
We have more general quality meeting every month.

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